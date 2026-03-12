import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from sqlalchemy import delete

from .connection_to_database import db_session, try_advisory_lock, advisory_unlock
from .table_models import Purchase

from goszakupki_requests.data_request import get_docs_by_region, download_archive_from_result
from goszakupki_requests.parse_data_fz_223 import parse_zip_archive

logger = logging.getLogger(__name__)

LOCK_KEY = int(os.getenv("SCHEDULER_LOCK_KEY", "424242"))

ORG_REGION = os.getenv("ORG_REGION", "77")
DOCUMENT_TYPE = os.getenv("DOCUMENT_TYPE_223", "purchaseNotice")
SUBSYSTEM_TYPE = os.getenv("SUBSYSTEM_TYPE", "RI223")

BACKFILL_DAYS = int(os.getenv("BACKFILL_DAYS", "10"))
BACKFILL_ON_STARTUP = os.getenv("PIPELINE_BACKFILL_ON_STARTUP", "true").lower() == "true"

# по вашему решению: просроченные = submission_close_datetime < now()
EXPIRE_MODE = os.getenv("EXPIRE_MODE", "now")  # now | start_of_today

# in-memory статус (простая телеметрия)
LAST_JOB_STATUS: Dict[str, Any] = {
    "running": False,
    "job": None,
    "started_at": None,
    "finished_at": None,
    "message": "idle",
    "progress": None,
    "result": None,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _set_status(**kwargs):
    LAST_JOB_STATUS.update(kwargs)


def _parse_dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None
    return None


def get_last_status() -> Dict[str, Any]:
    return LAST_JOB_STATUS


def delete_expired(db, mode: str = "now") -> int:
    now = _utcnow()
    if mode == "start_of_today":
        cutoff = datetime(now.year, now.month, now.day, tzinfo=timezone.utc).replace(tzinfo=None)
    else:
        cutoff = now.replace(tzinfo=None)

    stmt = (
        delete(Purchase)
        .where(Purchase.submission_close_datetime.isnot(None))
        .where(Purchase.submission_close_datetime < cutoff)
    )
    res = db.execute(stmt)
    return res.rowcount or 0


def process_day(date_str: str) -> int:
    logger.info("Pipeline: обработка даты %s", date_str)

    result = get_docs_by_region(
        org_region=ORG_REGION,
        document_type=DOCUMENT_TYPE,
        exact_date=date_str,
        subsystem_type=SUBSYSTEM_TYPE,
    )

    zip_path = download_archive_from_result(result)
    logger.info("Pipeline: архив скачан: %s", zip_path)

    purchases = parse_zip_archive(zip_path)
    logger.info("Pipeline: после фильтров закупок: %s", len(purchases))

    if not purchases:
        return 0

    saved = 0
    with db_session() as db:
        for p in purchases:
            guid = p.get("guid")
            if not guid:
                continue

            if db.get(Purchase, guid):
                continue

            obj = Purchase(
                guid=guid,
                registration_number=p.get("registration_number"),
                name=p.get("name") or "",
                source_file=p.get("source_file"),
                initial_sum=p.get("initial_sum"),
                publication_datetime=_parse_dt(p.get("publication_datetime")),
                submission_close_datetime=_parse_dt(p.get("submission_close_datetime")),
                customer=p.get("customer") or {},
                contact=p.get("contact") or {},
                apply_request=p.get("apply_request") or {},
                lots=p.get("lots") or [],
            )
            db.add(obj)
            saved += 1

    logger.info("Pipeline: сохранено за %s: %s", date_str, saved)
    return saved


def run_daily_job() -> Dict[str, Any]:
    with db_session() as db:
        if not try_advisory_lock(db, LOCK_KEY):
            msg = "Scheduler: lock занят, пропускаю запуск daily"
            logger.info(msg)
            return {"ok": False, "skipped": True, "reason": "lock_busy"}

    _set_status(running=True, job="daily", started_at=_utcnow().isoformat(), finished_at=None, message="running", progress=None, result=None)

    try:
        yesterday = (_utcnow() - timedelta(days=1)).date()
        date_str = yesterday.strftime("%Y-%m-%d")

        _set_status(progress={"date": date_str})
        added = process_day(date_str)

        with db_session() as db:
            deleted = delete_expired(db, mode=EXPIRE_MODE)

        result = {"ok": True, "added": added, "deleted_expired": deleted, "date": date_str}
        _set_status(running=False, finished_at=_utcnow().isoformat(), message="done", result=result)
        logger.info("Scheduler: daily done | %s", result)
        return result

    except Exception as e:
        logger.exception("Scheduler: daily job failed")
        _set_status(running=False, finished_at=_utcnow().isoformat(), message=f"error: {e}", result={"ok": False, "error": str(e)})
        return {"ok": False, "error": str(e)}

    finally:
        with db_session() as db:
            advisory_unlock(db, LOCK_KEY)


def run_backfill(days: int | None = None) -> Dict[str, Any]:
    days = int(days or BACKFILL_DAYS)

    with db_session() as db:
        if not try_advisory_lock(db, LOCK_KEY):
            msg = "Scheduler(backfill): lock занят, пропускаю backfill"
            logger.info(msg)
            return {"ok": False, "skipped": True, "reason": "lock_busy"}

    _set_status(
        running=True,
        job="backfill",
        started_at=_utcnow().isoformat(),
        finished_at=None,
        message="running",
        progress={"days": days, "current": 0, "date": None, "added_total": 0},
        result=None,
    )

    added_total = 0
    processed_days = 0

    try:
        today = _utcnow().date()
        start = today - timedelta(days=days)

        for i in range(days):
            d = start + timedelta(days=i)
            if d >= today:
                continue

            date_str = d.strftime("%Y-%m-%d")
            processed_days += 1

            _set_status(progress={"days": days, "current": i + 1, "date": date_str, "added_total": added_total})
            logger.info("Backfill: day %s/%s | %s", i + 1, days, date_str)

            added = process_day(date_str)
            added_total += added

        with db_session() as db:
            deleted = delete_expired(db, mode=EXPIRE_MODE)

        result = {"ok": True, "processed_days": processed_days, "added_total": added_total, "deleted_expired": deleted}
        _set_status(running=False, finished_at=_utcnow().isoformat(), message="done", result=result)
        logger.info("Scheduler(backfill): done | %s", result)
        return result

    except Exception as e:
        logger.exception("Scheduler(backfill) failed")
        _set_status(running=False, finished_at=_utcnow().isoformat(), message=f"error: {e}", result={"ok": False, "error": str(e)})
        return {"ok": False, "error": str(e)}

    finally:
        with db_session() as db:
            advisory_unlock(db, LOCK_KEY)


def run_backfill_on_startup() -> None:
    if not BACKFILL_ON_STARTUP:
        logger.info("Backfill on startup disabled")
        return
    run_backfill(BACKFILL_DAYS)