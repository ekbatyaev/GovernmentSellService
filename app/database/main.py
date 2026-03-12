import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .connection_to_database import init_db, get_db
from .table_models import Purchase
from .scheduler import run_backfill_on_startup, run_daily_job, run_backfill, delete_expired, get_last_status

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

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Zakupki Database API",
    description="API для управления госзакупками",
    version="1.0.0",
)

# Вариант A: в контейнере после `COPY app .` статика лежит в /app/static
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------
# Pydantic models
# ---------------------------

class PutPurchaseModel(BaseModel):
    token: str
    guid: str
    registration_number: Optional[str] = None
    name: str
    source_file: Optional[str] = None
    initial_sum: Optional[float] = None
    publication_datetime: Optional[datetime] = None
    submission_close_datetime: Optional[datetime] = None
    customer: Any
    contact: Any
    apply_request: Any
    lots: List[Any]


class DeletePurchaseModel(BaseModel):
    token: str
    guid: str


class GetPurchaseModel(BaseModel):
    token: str
    guid: str


class GetAllPurchasesModel(BaseModel):
    token: str
    name: Optional[str] = None
    initial_sum_from: Optional[float] = None
    initial_sum_to: Optional[float] = None
    publication_datetime_from: Optional[datetime] = None
    publication_datetime_to: Optional[datetime] = None
    submission_close_datetime_from: Optional[datetime] = None
    submission_close_datetime_to: Optional[datetime] = None
    source_file: Optional[str] = None


class UpdatePurchaseModel(BaseModel):
    token: str
    guid: str
    registration_number: Optional[str] = None
    name: Optional[str] = None
    source_file: Optional[str] = None
    initial_sum: Optional[float] = None
    publication_datetime: Optional[datetime] = None
    submission_close_datetime: Optional[datetime] = None
    customer: Optional[Any] = None
    contact: Optional[Any] = None
    apply_request: Optional[Any] = None
    lots: Optional[Any] = None


class PurchaseResponseModel(BaseModel):
    guid: str
    registration_number: Optional[str]
    name: str
    source_file: Optional[str]
    initial_sum: Optional[float]
    publication_datetime: Optional[datetime]
    submission_close_datetime: Optional[datetime]
    customer: Any
    contact: Any
    apply_request: Any
    lots: List[Any]

    class Config:
        from_attributes = True


class SuccessResponseModel(BaseModel):
    status: str
    message: str
    data: Optional[Any] = None


def verify_token(token: str):
    if SYSTEM_TOKEN != token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ---------------------------
# Scheduler
# ---------------------------

scheduler: BackgroundScheduler | None = None


def _create_scheduler() -> BackgroundScheduler:
    s = BackgroundScheduler(timezone=MOSCOW_TZ)
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


@app.get("/config")
async def get_config():
    return {
        "system_token": SYSTEM_TOKEN
    }

# ---------------------------
# Routes
# ---------------------------

@app.get("/")
async def root():
    # Вариант A: файл лежит в /app/static/index.html
    return FileResponse("static/index.html")


@app.post("/put_purchase", response_model=SuccessResponseModel, status_code=status.HTTP_201_CREATED)
def put_purchase(purchase_data: PutPurchaseModel, db: Session = Depends(get_db)):
    verify_token(purchase_data.token)

    new_purchase = Purchase(
        guid=purchase_data.guid,
        registration_number=purchase_data.registration_number,
        name=purchase_data.name,
        source_file=purchase_data.source_file,
        initial_sum=purchase_data.initial_sum,
        publication_datetime=purchase_data.publication_datetime,
        submission_close_datetime=purchase_data.submission_close_datetime,
        customer=purchase_data.customer or {},
        contact=purchase_data.contact or {},
        apply_request=purchase_data.apply_request or {},
        lots=purchase_data.lots or [],
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
        existing = db.get(Purchase, purchase_data.guid)
        if existing:
            return SuccessResponseModel(
                status="success",
                message="Purchase already exists",
                data=PurchaseResponseModel.from_orm(existing),
            )
        raise HTTPException(status_code=400, detail="Failed to create purchase")


@app.post("/delete_purchase", response_model=SuccessResponseModel)
def delete_purchase(purchase_data: DeletePurchaseModel, db: Session = Depends(get_db)):
    verify_token(purchase_data.token)

    purchase = db.get(Purchase, purchase_data.guid)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    db.delete(purchase)
    db.commit()
    return SuccessResponseModel(status="success", message="Deleted", data={"guid": purchase_data.guid})


@app.post("/get_purchase", response_model=SuccessResponseModel)
def get_purchase(purchase_data: GetPurchaseModel, db: Session = Depends(get_db)):
    verify_token(purchase_data.token)

    purchase = db.get(Purchase, purchase_data.guid)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    return SuccessResponseModel(
        status="success",
        message="Ok",
        data=PurchaseResponseModel.from_orm(purchase),
    )


@app.post("/get_all_purchases", response_model=SuccessResponseModel)
def get_all_purchases(purchase_data: GetAllPurchasesModel, db: Session = Depends(get_db)):
    verify_token(purchase_data.token)

    query = select(Purchase)

    if purchase_data.name:
        query = query.where(Purchase.name.ilike(f"%{purchase_data.name}%"))

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

    sub_from = purchase_data.submission_close_datetime_from
    sub_to = purchase_data.submission_close_datetime_to
    if sub_from and sub_to:
        if sub_from.date() == sub_to.date():
            start = datetime.combine(sub_from.date(), datetime.min.time())
            end = start + timedelta(days=1)
            query = query.where(Purchase.submission_close_datetime >= start, Purchase.submission_close_datetime < end)
        else:
            query = query.where(Purchase.submission_close_datetime >= sub_from, Purchase.submission_close_datetime <= sub_to)
    elif sub_from:
        query = query.where(Purchase.submission_close_datetime >= sub_from)
    elif sub_to:
        query = query.where(Purchase.submission_close_datetime <= sub_to)

    if purchase_data.source_file:
        query = query.where(Purchase.source_file.ilike(f"%{purchase_data.source_file}%"))

    query = query.order_by(Purchase.publication_datetime.desc().nullslast())

    purchases = db.scalars(query).all()
    data = [PurchaseResponseModel.from_orm(p) for p in purchases]
    return SuccessResponseModel(status="success", message=f"Found {len(data)} purchases", data=data)


@app.post("/update_purchase", response_model=SuccessResponseModel)
def update_purchase(purchase_data: UpdatePurchaseModel, db: Session = Depends(get_db)):
    verify_token(purchase_data.token)

    purchase = db.get(Purchase, purchase_data.guid)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    update_data = purchase_data.model_dump(exclude_unset=True, exclude={"token", "guid"})
    for field, value in update_data.items():
        if value is not None:
            setattr(purchase, field, value)

    db.commit()
    db.refresh(purchase)

    return SuccessResponseModel(
        status="success",
        message="Updated",
        data=PurchaseResponseModel.from_orm(purchase),
    )


@app.get("/stats", response_model=SuccessResponseModel)
def get_statistics(db: Session = Depends(get_db)):
    purchases_count = db.scalar(select(func.count()).select_from(Purchase))
    return SuccessResponseModel(
        status="success",
        message="Statistics",
        data={"purchases_count": purchases_count, "timestamp": datetime.utcnow().isoformat()},
    )


@app.get("/health", response_model=SuccessResponseModel)
def health_check(db: Session = Depends(get_db)):
    db.execute(select(1))
    return SuccessResponseModel(status="success", message="Healthy")


# ---- Admin endpoints ----

class AdminTokenModel(BaseModel):
    token: str


@app.post("/admin/run_daily", response_model=SuccessResponseModel)
def admin_run_daily(body: AdminTokenModel):
    verify_token(body.token)
    result = run_daily_job()
    return SuccessResponseModel(status="success", message="Daily finished", data=result)


class AdminBackfillModel(BaseModel):
    token: str
    days: Optional[int] = None


@app.post("/admin/run_backfill", response_model=SuccessResponseModel)
def admin_run_backfill(body: AdminBackfillModel):
    verify_token(body.token)
    result = run_backfill(days=body.days)
    return SuccessResponseModel(status="success", message="Backfill finished", data=result)


@app.get("/admin/job_status", response_model=SuccessResponseModel)
def admin_job_status():
    # без токена специально: можно закрыть, если хотите
    return SuccessResponseModel(status="success", message="Ok", data=get_last_status())

class DeleteExpiredModel(BaseModel):
    token: str


@app.post("/admin/delete_expired", response_model=SuccessResponseModel)
def admin_delete_expired(body: DeleteExpiredModel, db: Session = Depends(get_db)):
    verify_token(body.token)
    deleted = delete_expired(db, mode=os.getenv("EXPIRE_MODE", "now"))
    db.commit()
    return SuccessResponseModel(status="success", message="Expired deleted", data={"deleted": deleted})