from datetime import datetime
from fastapi import BackgroundTasks
from fastapi import APIRouter
from app.routers.dependencies import require_token
from app.routers.schemas import ResponseModel
from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.backend.db.settings import get_db
from app.routers.services.schemas import ProcessDayService, ProcessPeriodService
from sqlalchemy import select, func
from app.backend.functions import start_job, process_day, process_period, current_job
from app.settings import MOSCOW_TZ
from app.backend.db.models import NoticeDatabase, NewsLetterDatabase

service_router = APIRouter(prefix = "/services", tags=["services"], dependencies=[Depends(require_token)])

last_process_day_at, last_backfill_at = None, None

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

@service_router.get("/stats/job_status", response_model = ResponseModel, status_code = status.HTTP_200_OK)
async def get_job_status():
    return ResponseModel(status_message="success", data = current_job)

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

@service_router.get(f"/health", response_model=ResponseModel)
async def health_check(db: AsyncSession = Depends(get_db)):
    await db.execute(select(1))
    return ResponseModel(status_message="success", data = {})