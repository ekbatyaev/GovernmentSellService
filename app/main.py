import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Any
import random
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .connection_to_database import init_db, get_db
from .table_models import Purchase, NewsLetter
from .scheduler import run_backfill_on_startup, run_daily_job, run_backfill, delete_expired, get_last_status, \
    process_day

from .email_handles import send_email

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from zoneinfo import ZoneInfo

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

load_dotenv()

SYSTEM_TOKEN = os.getenv("SYSTEM_TOKEN")
if not SYSTEM_TOKEN:
    raise RuntimeError("SYSTEM_TOKEN is required")

DAILY_HOUR_MSK = int(os.getenv("DAILY_JOB_HOUR_MSK", "1"))
DAILY_MINUTE_MSK = int(os.getenv("DAILY_JOB_MINUTE_MSK", "0"))

API_BASE = os.getenv("API_BASE")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Zakupki Database API",
    description="API для управления госзакупками",
    version="1.0.0",
)


app.mount(
    f"{API_BASE}/assets",
    StaticFiles(directory="static/assets"),
    name="assets",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статистика

last_backfill_at = None
last_process_day_at = None

# Загрузка данных
def load_data(data_file):
    try:
        with open(data_file, 'r', encoding='utf-8') as file:
            return json.load(file)
    except:
        return {}

# Сохранение данных
def save_data(data_file, data):
    with open(data_file, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)



def verify_token(token: str):
    if SYSTEM_TOKEN != token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ---------------------------
# Scheduler
# ---------------------------

scheduler: BackgroundScheduler | None = None


def _create_scheduler() -> BackgroundScheduler:
    s = BackgroundScheduler(timezone=MOSCOW_TZ)
    global last_process_day_at
    last_process_day_at = datetime.now(MOSCOW_TZ).isoformat()
    s.add_job(
        run_daily_job,
        trigger=CronTrigger(hour=DAILY_HOUR_MSK, minute=DAILY_MINUTE_MSK, timezone=MOSCOW_TZ),
        id="daily_pipeline",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    return s

@app.on_event("startup")
def startup_event():
    global scheduler
    init_db()

    scheduler = _create_scheduler()
    scheduler.start()

    # backfill 10 дней назад при старте

    run_backfill_on_startup()

    logger.info("Startup complete (db + scheduler)")


@app.on_event("shutdown")
def shutdown_event():
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
        scheduler = None


@app.get(f"{API_BASE}/config", response_model=SuccessResponseModel)
async def get_config():
    return SuccessResponseModel(
        status="success",
        message="Config",
        data={
            "system_token": SYSTEM_TOKEN,
        },
    )

# ---------------------------
# Routes
# ---------------------------

@app.get(f"{API_BASE}/")
async def root():
    # Вариант A: файл лежит в /app/static/index.html
    return FileResponse("static/index.html")


@app.post(f"{API_BASE}/put_purchase", response_model=SuccessResponseModel, status_code=status.HTTP_201_CREATED)
def put_purchase(purchase_data: PutPurchaseModel, db: Session = Depends(get_db)):
    verify_token(purchase_data.token)

    query = select(Purchase).where(Purchase.registration_number == purchase_data.registration_number)

    query = query.where(Purchase.filter_type_name == purchase_data.filter_type_name)

    existing_purchase = db.scalar(query)

    if existing_purchase:
        existing_purchase.guid = purchase_data.guid
        existing_purchase.registration_number = purchase_data.registration_number
        existing_purchase.name = purchase_data.name
        existing_purchase.source_file = purchase_data.source_file
        existing_purchase.initial_sum = purchase_data.initial_sum
        existing_purchase.publication_datetime = purchase_data.publication_datetime
        existing_purchase.submission_start_datetime = purchase_data.submission_start_datetime
        existing_purchase.submission_close_datetime = purchase_data.submission_close_datetime
        existing_purchase.customer = purchase_data.customer or {}
        existing_purchase.contact = purchase_data.contact or {}
        existing_purchase.apply_request = purchase_data.apply_request or {}
        existing_purchase.result_info = purchase_data.result_info or {}
        existing_purchase.documents_list = purchase_data.documents_list or []
        existing_purchase.lots = purchase_data.lots or []

        existing_purchase.filter_type_name = purchase_data.filter_type_name
        existing_purchase.region_number = purchase_data.region_number

        db.commit()
        db.refresh(existing_purchase)

        return SuccessResponseModel(
            status="success",
            message="Purchase updated",
            data=PurchaseResponseModel.from_orm(existing_purchase),
        )

    new_purchase = Purchase(
        guid=purchase_data.guid,
        registration_number=purchase_data.registration_number,
        name=purchase_data.name,
        source_file=purchase_data.source_file,
        initial_sum=purchase_data.initial_sum,
        publication_datetime=purchase_data.publication_datetime,
        submission_start_datetime=purchase_data.submission_start_datetime,
        submission_close_datetime=purchase_data.submission_close_datetime,
        customer=purchase_data.customer or {},
        contact=purchase_data.contact or {},
        apply_request=purchase_data.apply_request or {},
        result_info=purchase_data.result_info or {},
        documents_list=purchase_data.documents_list or [],
        lots=purchase_data.lots or [],
        filter_type_name=purchase_data.filter_type_name,
        region_number=purchase_data.region_number
    )

    try:
        db.add(new_purchase)
        db.commit()
        db.refresh(new_purchase)
        return SuccessResponseModel(
            status="success",
            message="Purchase created",
            data=PurchaseResponseModel.from_orm(new_purchase),
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to create purchase")


@app.post(f"{API_BASE}/delete_purchase", response_model=SuccessResponseModel)
def delete_purchase(purchase_data: DeletePurchaseModel, db: Session = Depends(get_db)):
    verify_token(purchase_data.token)

    purchase = db.get(Purchase, purchase_data.guid)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    db.delete(purchase)
    db.commit()
    return SuccessResponseModel(status="success", message="Deleted", data={"guid": purchase_data.guid})


@app.post(f"{API_BASE}/get_purchase", response_model=SuccessResponseModel)
def get_purchase(purchase_data: GetPurchaseModel, db: Session = Depends(get_db)):
    verify_token(purchase_data.token)

    query = db.query(Purchase)

    if purchase_data.registration_number:
        query = query.filter(Purchase.registration_number == purchase_data.registration_number.strip())

    # Если есть guid — добавляем условие (если это не первичный ключ, используем .filter)
    if purchase_data.guid:
        query = query.filter(Purchase.guid == purchase_data.guid.strip())

    # Интегрируем вашу фильтрацию по типу
    if purchase_data.filter_type_name:
        query = query.filter(Purchase.filter_type_name == purchase_data.filter_type_name)

    if not purchase_data.guid and not purchase_data.registration_number:
        raise HTTPException(
            status_code=400,
            detail="Не передан ни один ключ поиска: guid или registration_number",
        )

    # 4. Выполняем запрос в БД
    purchase = query.first()

    if not purchase:
        return SuccessResponseModel(
            status="success",
            message="Purchase not found",
            data={},
        )

    return SuccessResponseModel(
        status="success",
        message="Ok",
        data=PurchaseResponseModel.from_orm(purchase),
    )



@app.post(f"{API_BASE}/get_all_purchases", response_model=SuccessResponseModel)
def get_all_purchases(purchase_data: GetAllPurchasesModel, db: Session = Depends(get_db)):
    verify_token(purchase_data.token)
    print(purchase_data)
    query = select(Purchase)

    if purchase_data.name:
        query = query.where(Purchase.name.ilike(f"%{purchase_data.name}%"))

    if purchase_data.filter_type_name:
        query = query.where(Purchase.filter_type_name == purchase_data.filter_type_name)

    if purchase_data.filter_type_name == "Тендеры для OEM" and purchase_data.oem_flag:
        query = query.where(Purchase.result_info["Слова маячки в тз"].astext == purchase_data.oem_flag)

    if purchase_data.filter_type_name == "Тендеры для ITM" and purchase_data.itm_option:
        query = query.where(Purchase.result_info["Категория заявки"].astext == purchase_data.itm_option)

    if purchase_data.region_numbers:
        query = query.where(Purchase.region_number.in_(purchase_data.region_numbers))
    elif purchase_data.region_number is not None:
        query = query.where(Purchase.region_number == purchase_data.region_number)

    if purchase_data.initial_sum_from is not None:
        query = query.where(Purchase.initial_sum >= purchase_data.initial_sum_from)
    if purchase_data.initial_sum_to is not None:
        query = query.where(Purchase.initial_sum <= purchase_data.initial_sum_to)

    pub_from = purchase_data.publication_datetime_from
    pub_to = purchase_data.publication_datetime_to
    if pub_from and pub_to:
        if pub_from.date() == pub_to.date():
            start = datetime.combine(pub_from.date(), datetime.min.time())
            end = start + timedelta(days=1)
            query = query.where(Purchase.publication_datetime >= start, Purchase.publication_datetime < end)
        else:
            query = query.where(Purchase.publication_datetime >= pub_from, Purchase.publication_datetime <= pub_to)
    elif pub_from:
        query = query.where(Purchase.publication_datetime >= pub_from)
    elif pub_to:
        query = query.where(Purchase.publication_datetime <= pub_to)

    submission_start_datetime_from = purchase_data.submission_start_datetime_from
    submission_start_datetime_to = purchase_data.submission_start_datetime_to

    if submission_start_datetime_from and submission_start_datetime_to:
        if submission_start_datetime_from.date() == submission_start_datetime_to.date():
            start = datetime.combine(submission_start_datetime_from.date(), datetime.min.time())
            end = start + timedelta(days=1)
            query = query.where(
                Purchase.submission_start_datetime >= start,
                Purchase.submission_start_datetime < end
            )
        else:
            end = datetime.combine(submission_start_datetime_to.date(), datetime.min.time()) + timedelta(days=1)
            query = query.where(
                Purchase.submission_start_datetime >= submission_start_datetime_from,
                Purchase.submission_start_datetime < end
            )

    elif submission_start_datetime_from:
        query = query.where(Purchase.submission_start_datetime >= submission_start_datetime_from)

    elif submission_start_datetime_to:
        end = datetime.combine(submission_start_datetime_to.date(), datetime.min.time()) + timedelta(days=1)
        query = query.where(Purchase.submission_start_datetime < end)

    submission_close_datetime_from = purchase_data.submission_close_datetime_from
    submission_close_datetime_to = purchase_data.submission_close_datetime_to

    if submission_close_datetime_from and submission_close_datetime_to:
        if submission_close_datetime_from.date() == submission_close_datetime_to.date():
            start = datetime.combine(submission_close_datetime_from.date(), datetime.min.time())
            end = start + timedelta(days=1)
            query = query.where(
                Purchase.submission_close_datetime >= start,
                Purchase.submission_close_datetime < end
            )
        else:
            end = datetime.combine(submission_close_datetime_to.date(), datetime.min.time()) + timedelta(days=1)
            query = query.where(
                Purchase.submission_close_datetime >= submission_close_datetime_from,
                Purchase.submission_close_datetime < end
            )

    elif submission_close_datetime_from:
        query = query.where(Purchase.submission_close_datetime >= submission_close_datetime_from)

    elif submission_close_datetime_to:
        end = datetime.combine(submission_close_datetime_to.date(), datetime.min.time()) + timedelta(days=1)
        query = query.where(Purchase.submission_close_datetime < end)

    if purchase_data.source_file:
        query = query.where(Purchase.source_file.ilike(f"%{purchase_data.source_file}%"))

    query = query.order_by(Purchase.publication_datetime.desc().nullslast())

    purchases = db.scalars(query).all()
    data = [PurchaseResponseModel.from_orm(p) for p in purchases]
    return SuccessResponseModel(status="success", message=f"Found {len(data)} purchases", data=data)


@app.post(f"{API_BASE}/update_purchase", response_model=SuccessResponseModel)
def update_purchase(purchase_data: UpdatePurchaseModel, db: Session = Depends(get_db)):
    verify_token(purchase_data.token)

    guid = purchase_data.guid.strip() if purchase_data.guid else None
    registration_number = (
        purchase_data.registration_number.strip()
        if purchase_data.registration_number
        else None
    )

    if guid:
        purchase = db.query(Purchase).filter(Purchase.guid == guid).first()
    elif registration_number:
        purchase = db.query(Purchase).filter(Purchase.registration_number == registration_number).first()
    else:
        raise HTTPException(
            status_code=400,
            detail="Не передан ни один ключ поиска: guid или registration_number",
        )

    # Если даже при наличии одного из ключей запись не найдена в БД
    if not purchase:
        return SuccessResponseModel(
            status="success",
            message="Purchase not found",
            data={}
        )

    if purchase_data.filter_type_name and purchase.filter_type_name != purchase_data.filter_type_name:
        purchase = None

    if not purchase:
         return SuccessResponseModel(
            status="success",
            message="Purchase not found",
            data={},
        )

    update_data = purchase_data.model_dump(exclude_unset=True, exclude={"token", "guid", "registration_number"})
    for field, value in update_data.items():
        if value is not None:
            setattr(purchase, field, value)

    try:
        db.commit()
        db.refresh(purchase)
    except Exception:
        db.rollback()
        raise

    return SuccessResponseModel(
        status="success",
        message="Updated",
        data=PurchaseResponseModel.from_orm(purchase),
    )



@app.get(f"{API_BASE}/stats", response_model=SuccessResponseModel)
def get_statistics(db: Session = Depends(get_db)):
    global last_backfill_at, last_process_day_at
    purchases_count = db.scalar(select(func.count()).select_from(Purchase))
    newsletter_count = db.scalar(select(func.count()).select_from(NewsLetter))
    return SuccessResponseModel(
        status="success",
        message="Statistics",
        data={"purchases_count": purchases_count, "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
              "newsletter_count": newsletter_count, "last_backfill_at": last_backfill_at,"last_process_day_at": last_process_day_at})


@app.get(f"{API_BASE}/health", response_model=SuccessResponseModel)
def health_check(db: Session = Depends(get_db)):
    db.execute(select(1))
    return SuccessResponseModel(status="success", message="Healthy")


# ---- Admin endpoints ----

@app.post(f"{API_BASE}/admin/run_process_day", response_model=SuccessResponseModel)
def admin_run_process_day(body: AdminProcessDay):
    verify_token(body.token)
    global last_process_day_at
    print(body.date)
    date_str = body.date.strftime("%Y-%m-%d")
    last_process_day_at = datetime.now(MOSCOW_TZ).isoformat()
    result = process_day(date_str, filter_number = body.filter_number)
    return SuccessResponseModel(status="success", message="Process day finished", data=result)

@app.post(f"{API_BASE}/admin/run_backfill", response_model=SuccessResponseModel)
def admin_run_backfill(body: AdminBackfillModel):
    verify_token(body.token)
    global last_backfill_at
    last_backfill_at = datetime.now(MOSCOW_TZ).isoformat()
    result = run_backfill(days=body.days, filter_number=body.filter_number)
    return SuccessResponseModel(status="success", message="Backfill finished", data=result)

@app.post(f"{API_BASE}/admin/run_backfill_period_of_time", response_model=SuccessResponseModel)
def admin_run_process_period_of_type(body: AdminProcessPeriodOfTime):
    verify_token(body.token)
    global last_process_day_at
    date_from, date_to = body.date_from, body.date_to
    result = []
    last_process_day_at = datetime.now(MOSCOW_TZ).isoformat()
    logger.info(f"Processing period of time from {date_from.strftime("%Y-%m-%d")} to {date_to.strftime("%Y-%m-%d")} have started")
    while date_from < date_to:
        result.append(process_day(date_from.strftime("%Y-%m-%d"), filter_number = body.filter_number))
        date_from += timedelta(days=1)
    return SuccessResponseModel(status="success", message=f"Processing period of time successfully completed", data=result)

@app.get(f"{API_BASE}/admin/job_status", response_model=SuccessResponseModel)
def admin_job_status():
    # без токена специально: можно закрыть, если хотите
    return SuccessResponseModel(status="success", message="Ok", data=get_last_status())

@app.post(f"{API_BASE}/admin/delete_expired", response_model=SuccessResponseModel)
def admin_delete_expired(body: DeleteExpiredModel, db: Session = Depends(get_db)):
    verify_token(body.token)
    deleted = delete_expired(db)
    db.commit()
    return SuccessResponseModel(status="success", message="Expired deleted", data={"deleted": deleted})

@app.post(f"{API_BASE}/put_newsletter", response_model=SuccessResponseModel, status_code=status.HTTP_201_CREATED)
def put_newsletter(data: PutNewsLetterModel, db: Session = Depends(get_db)):
    verify_token(data.token)

    newsletter = NewsLetter(
        email=data.email,
        filter_type_name=data.filter_type_name,
        district_name=data.district_name,
    )

    try:
        db.add(newsletter)
        db.commit()
        db.refresh(newsletter)

        return SuccessResponseModel(
            status="success",
            message="Email added",
            data={
                "email": newsletter.email,
                "filter_type_name": newsletter.filter_type_name,
                "district_name": newsletter.district_name,
            },
        )

    except IntegrityError:
        db.rollback()

        existing = db.query(NewsLetter).filter_by(email=data.email).first()
        if existing:
            return SuccessResponseModel(
                status="success",
                message="Email already exists",
                data={
                    "email": existing.email,
                    "filter_type_name": existing.filter_type_name,
                    "district_name": existing.district_name,
                },
            )

        raise HTTPException(status_code=400, detail="Failed to add email")

@app.post(f"{API_BASE}/delete_newsletter", response_model=SuccessResponseModel)
def delete_newsletter(data: DeleteNewsLetterModel, db: Session = Depends(get_db)):
    verify_token(data.token)

    query = db.query(NewsLetter).filter(NewsLetter.email == data.email)

    if data.filter_type_name:
        query = query.filter(NewsLetter.filter_type_name == data.filter_type_name)

    newsletters = query.all()

    if not newsletters:
        raise HTTPException(status_code=404, detail="Email not found")

    if len(newsletters) > 1 and not data.filter_type_name:
        raise HTTPException(
            status_code=400,
            detail="У email несколько подписок. Передайте filter_type_name для удаления конкретной подписки.",
        )

    for newsletter in newsletters:
        db.delete(newsletter)

    db.commit()

    return SuccessResponseModel(
        status="success",
        message="Deleted",
        data={
            "email": data.email,
            "deleted_count": len(newsletters),
        },
    )

@app.post(f"{API_BASE}/get_newsletter", response_model=SuccessResponseModel)
def get_newsletter(data: GetNewsLetterModel, db: Session = Depends(get_db)):
    verify_token(data.token)

    query = db.query(NewsLetter).filter(NewsLetter.email == data.email)

    if data.filter_type_name:
        query = query.filter(NewsLetter.filter_type_name == data.filter_type_name)

    if data.district_name:
        query = query.filter(NewsLetter.district_name == data.district_name)

    newsletters = query.all()

    if not newsletters:
        raise HTTPException(status_code=404, detail="Email not found")

    result = [
        {
            "email": n.email,
            "filter_type_name": n.filter_type_name,
            "district_name": n.district_name,
        }
        for n in newsletters
    ]

    return SuccessResponseModel(
        status="success",
        message="Ok",
        data=result,
    )

@app.post(f"{API_BASE}/get_all_newsletters", response_model=SuccessResponseModel)
def get_all_newsletters(data: GetAllNewsLettersModel, db: Session = Depends(get_db)):
    verify_token(data.token)

    query = db.query(NewsLetter)

    if data.filter_type_name:
        query = query.filter(NewsLetter.filter_type_name == data.filter_type_name)

    if data.district_name:
        query = query.filter(NewsLetter.district_name == data.district_name)

    newsletters = query.all()

    result = [n.email  for n in newsletters]

    return SuccessResponseModel(

        status="success",

        message="Ok",

        data=result,
    )

@app.post(f"{API_BASE}/send_auth_code", response_model=SuccessResponseModel)
def send_auth_code(data: SendAuthCode):
    verify_token(data.token)

    code = random.randint(100000, 999999)

    try:
        subject = "Проверочный код"
        html_content = f"""
        <html>
          <body style="font-family: Arial, sans-serif; line-height: 1.5; color: #333;">
            <h2 style="color:#2E86C1;">Проверочный код для рассылки Госзакупок</h2>
            <p>Здравствуйте!</p>
            <p>Ваш проверочный код для вашего email:</p>
            <p style="font-size: 1.5em; font-weight: bold; color:#E74C3C;">{code}</p>
            <p>Введите этот код в приложении, чтобы подтвердить или отменить рассылку.</p>
            <hr>
            <p style="font-size: 0.9em; color:#888;">
              Это письмо сформировано автоматически, отвечать на него не нужно.
            </p>
          </body>
        </html>
        """

        send_email(
            data.email,
            subject,
            html_content
        )
    except:
        raise HTTPException(status_code=500, detail="Email not found")

    try:
        codes_storage = load_data("auth_codes.json")
        codes_storage[data.email] = code
        save_data("auth_codes.json", codes_storage)
    except:
        raise HTTPException(status_code=500, detail="Code not saved")
    return SuccessResponseModel(
        status="success",
        message="Auth code created",
        data={"email": data.email},
    )

@app.post(f"{API_BASE}/verify_code", response_model=SuccessResponseModel)
def verify_code(data: VerifyCode):
    verify_token(data.token)
    try:
        codes_storage = load_data("auth_codes.json")
    except Exception:
        raise HTTPException(status_code=500, detail="Code data is not available")

    real_code = codes_storage.get(data.email)

    if real_code is None:
        raise HTTPException(status_code=404, detail="Code not found")

    if real_code != data.code:
        raise HTTPException(status_code=400, detail="Invalid code")

    del codes_storage[data.email]

    try:
        save_data("auth_codes.json", codes_storage)
    except:
        raise HTTPException(status_code=404, detail="Codes storage is not saved")

    return SuccessResponseModel(
        status="success",
        message="Auth completed",
        data={"auth": True}
    )

