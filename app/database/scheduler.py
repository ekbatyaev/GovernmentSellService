import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from sqlalchemy import delete
from .connection_to_database import db_session, try_advisory_lock, advisory_unlock
from .table_models import Purchase
from goszakupki_requests.data_request import get_docs_by_region, download_archive_from_result
from goszakupki_requests.parse_data_fz_223 import parse_zip_archive
import requests, pandas as pd
from .email_handles import send_email
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

LOCK_KEY = int(os.getenv("SCHEDULER_LOCK_KEY", "424242"))

ORG_REGION = os.getenv("ORG_REGION", "77")
DOCUMENT_TYPE = os.getenv("DOCUMENT_TYPE_223", "purchaseNotice")
SUBSYSTEM_TYPE = os.getenv("SUBSYSTEM_TYPE", "RI223")

BACKFILL_DAYS = int(os.getenv("BACKFILL_DAYS", "10"))
BACKFILL_ON_STARTUP = os.getenv("PIPELINE_BACKFILL_ON_STARTUP", "true").lower() == "true"

# по вашему решению: просроченные = submission_close_datetime < now()
EXPIRE_MODE = os.getenv("EXPIRE_MODE", "now")  # now | start_of_today

APP_URL = os.getenv("APP_URL")
TOKEN = os.getenv("SYSTEM_TOKEN") or exit("SYSTEM_TOKEN is required")

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

        now = datetime.now()
        start_day = datetime.combine(now.date(), datetime.time.min)

        emails = requests.post(f"{APP_URL}/get_all_newsletters", json={"token": TOKEN}).json().get("data", [])

        html_content = f"""
        <html><body style="font-family:Arial;">
        <h2 style="color:#2E86C1;">Уведомление о новых заявках с госзакупок</h2>
        <p>Добавлено новых заявок: <b style="color:#E74C3C;font-size:18px;">{added}</b></p>
        <hr><p style="color:#888;font-size:12px;">Это письмо сформировано автоматически, отвечать на него не нужно</p>
        </body></html>
        """

        data = requests.post(
            f"{APP_URL}/get_all_purchases",
            json={"token": TOKEN, "created_at_from": start_day.isoformat()}
        ).json().get("data", [])

        rows = []
        for p in data:
            base = {
                'guid_закупки': p['guid'],
                'reg_number': p['registration_number'],
                'название_закупки': p['name'],
                'файл_источник': p['source_file'],
                'сумма_общая': p['initial_sum'],
                'дата_публикации': p['publication_datetime'],
                'дата_окончания': p['submission_close_datetime'],
                'заказчик_инн': p['customer']['inn'],
                'заказчик_кпп': p['customer']['kpp'],
                'заказчик_огрн': p['customer']['ogrn'],
                'заказчик_название': p['customer']['full_name'],
                'контакт_email': p['contact']['email'],
                'контакт_телефон': p['contact']['phone'],
                'контакт_фио': " ".join(filter(None, [
                    p['contact']['last_name'],
                    p['contact']['first_name'],
                    p['contact']['middle_name']
                ])),
                'порядок_подачи': p['apply_request']['submission_order'],
                'место_подачи': p['apply_request']['submission_place'],
                'дата_начала_подачи': p['apply_request']['submission_start_date'],
            }

            for lot in p['lots']:
                for item in lot.get('items', [{}]):
                    rows.append({
                        **base,
                        'лот_guid': lot['guid'],
                        'лот_номер': lot['ordinal_number'],
                        'лот_предмет': lot['subject'],
                        'лот_валюта': lot['currency'],
                        'лот_сумма': lot['initial_sum'],
                        'позиция_количество': item.get('qty'),
                        'позиция_guid': item.get('guid'),
                        'окпд2_код': item.get('okpd2_code'),
                        'окпд2_название': item.get('okpd2_name'),
                        'доп_инфо': item.get('additional_info'),
                    })

        df = pd.DataFrame(rows)
        df.to_excel('analysis.xlsx', index=False)

        wb = load_workbook('analysis.xlsx')
        ws = wb.active

        # стили
        header_fill = PatternFill("solid", fgColor="366092")
        header_font = Font(color='FFFFFF', bold=True)
        cell_font = Font(size=10)
        align = Alignment(wrap_text=True, vertical='center')
        border = Border(*(Side(style='thin') for _ in range(4)))

        for col in range(1, ws.max_column + 1):
            c = ws.cell(1, col)
            c.font, c.fill, c.alignment, c.border = header_font, header_fill, align, border

        for r in range(2, ws.max_row + 1):
            ws.row_dimensions[r].height = 30
            for c in range(1, ws.max_column + 1):
                cell = ws.cell(r, c)
                cell.font, cell.alignment, cell.border = cell_font, align, border

        for col in range(1, ws.max_column + 1):
            letter = get_column_letter(col)
            max_len = max(len(str(ws.cell(r, col).value or "")) for r in range(1, ws.max_row + 1))
            ws.column_dimensions[letter].width = min(max_len + 2, 50)

        # сноска
        last = ws.max_row + 2
        ws.cell(last, 1, 'Сноска: данные по закупкам, лотам и позициям')
        ws.merge_cells(start_row=last, start_column=1, end_row=last, end_column=ws.max_column)

        f = ws.cell(last, 1)
        f.font = Font(italic=True, size=9, color='555555')
        f.alignment = Alignment(horizontal='center')
        f.border = Border(top=Side(style='thin', color='AAAAAA'))

        wb.save('analysis.xlsx')

        print("Файл создан")

        subject = f"Заявки с госзакупок за {now.strftime('%d.%m.%Y')}"

        for u in emails:
            if u.get("email"):
                send_email(u["email"], subject, html_content,
                           attachments=["analysis.xlsx"] if added else None)

        os.remove('analysis.xlsx')

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