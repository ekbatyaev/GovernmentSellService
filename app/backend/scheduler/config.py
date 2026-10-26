from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.settings import settings, MOSCOW_TZ
from app.backend.scheduler.tasks import daily_task

scheduler: AsyncIOScheduler | None = None

async def create_scheduler() -> AsyncIOScheduler:
    s = AsyncIOScheduler(timezone = MOSCOW_TZ)
    s.add_job(
        daily_task,
        trigger=CronTrigger(hour=settings.daily_job_hour_msk,
                            minute=settings.daily_job_minute_msk, timezone=MOSCOW_TZ),
        id="daily_pipeline",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    return s