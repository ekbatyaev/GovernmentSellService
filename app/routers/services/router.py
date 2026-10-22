import uuid
from datetime import datetime, timedelta
from random import randint
from fastapi import BackgroundTasks
from fastapi import APIRouter
from app.routers.dependencies import require_token
from app.routers.schemas import ResponseModel
from fastapi import Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.backend.db.settings import get_db
from app.routers.services.schemas import ProcessDayService, ProcessPeriodService
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.backend.functions import start_job, process_day, process_period, current_job, send_email, set_auth_code
from app.settings import MOSCOW_TZ
from app.backend.db.models import NoticeDatabase, NewsLetterDatabase, AuthCodeDatabase

service_router = APIRouter(prefix = "/services", tags=["services"], dependencies=[Depends(require_token)])

last_process_day_at, last_backfill_at = None, None

@service_router.get(f"/health", response_model=ResponseModel)
async def health_check(db: AsyncSession = Depends(get_db)):
    await db.execute(select(1))
    return ResponseModel(status_message="success", data = {})

@service_router.get("/stats", response_model = ResponseModel, status_code = status.HTTP_200_OK)
async def get_statistics(db: AsyncSession = Depends(get_db)):
    global last_backfill_at, last_process_day_at
    purchases_count = await db.scalar(select(func.count()).select_from(NoticeDatabase))
    newsletter_count = await db.scalar(select(func.count()).select_from(NewsLetterDatabase))
    return ResponseModel(
        status_message="success",
        data={"purchases_count": purchases_count, "timestamp": datetime.now(MOSCOW_TZ).replace(tzinfo=None).isoformat(),
              "newsletter_count": newsletter_count, "last_backfill_at": last_backfill_at,
              "last_process_day_at": last_process_day_at})

@service_router.get("/stats/job_status", response_model = ResponseModel, status_code = status.HTTP_200_OK)
async def get_job_status():
    return ResponseModel(status_message="success", data = current_job)

@service_router.post("/send_auth_code/{email}", response_model=ResponseModel, status_code=status.HTTP_200_OK)
async def send_auth_code(email: str, db: AsyncSession = Depends(get_db)):

    query = select(AuthCodeDatabase)
    query = query.where(AuthCodeDatabase.email == email)

    query = query.where(AuthCodeDatabase.created_at <= datetime.now(MOSCOW_TZ).replace(tzinfo=None) - timedelta(minutes=5))

    search_request = await db.execute(query)
    earlier_auth_code = search_request.scalar_one_or_none()

    if earlier_auth_code:
        raise HTTPException(status_code=500, detail="Подождите 5 минут перед тем как отправить другой проверочный код.")

    code = randint(100000, 999999)

    try:
        subject = "Проверочный код"
        html_content = f"""
            <html>
              <body style="font-family: Arial, sans-serif; line-height: 1.5; color: #333;">
                <h2 style="color:#2E86C1;">Проверочный код для рассылки Госзакупок</h2>
                <p>Здравствуйте!</p>
                <p>Ваш проверочный код для вашего newsletters:</p>
                <p style="font-size: 1.5em; font-weight: bold; color:#E74C3C;">{code}</p>
                <p>Введите этот код в приложении, чтобы подтвердить или отменить рассылку.</p>
                <hr>
                <p style="font-size: 0.9em; color:#888;">
                  Это письмо сформировано автоматически, отвечать на него не нужно.
                </p>
              </body>
            </html>
            """

        await send_email(
            email,
            subject,
            html_content
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Email not found")

    auth_code_guid = str(uuid.uuid4())
    new_auth_code = AuthCodeDatabase(guid = auth_code_guid, email = email,
                                     code = code, created_at = datetime.now(MOSCOW_TZ).replace(tzinfo=None),
                                     last_checked_at = datetime.now(MOSCOW_TZ).replace(tzinfo=None))

    try:
        db.add(new_auth_code)
        await db.commit()
        await db.refresh(new_auth_code)
        return ResponseModel(
            status_message="created",
            data={"guid": auth_code_guid}
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Code not saved")

@service_router.post("/run/process_day", response_model = ResponseModel, status_code = status.HTTP_200_OK)
async def run_process_day(process_day_info: ProcessDayService, background: BackgroundTasks):
    global last_process_day_at
    date_str = process_day_info.date.strftime("%Y-%m-%d")
    start_job(background, "run_process_day", process_day, date_str,
              filter_number=process_day_info.filter_number)
    last_process_day_at = datetime.now(MOSCOW_TZ).replace(tzinfo=None).isoformat()
    return ResponseModel(status_message="success", data = {"date": date_str})

@service_router.post("/run/process_period", response_model = ResponseModel, status_code = status.HTTP_200_OK)
async def run_process_period(process_period_info: ProcessPeriodService, background: BackgroundTasks):
    global last_process_day_at
    start_job(background, "run_process_period", process_period,
              process_period_info.date_from, process_period_info.date_to, process_period_info.filter_number)
    last_process_day_at = datetime.now(MOSCOW_TZ).replace(tzinfo=None).isoformat()
    return ResponseModel(status_message="success", data={**(process_period_info.model_dump())})
