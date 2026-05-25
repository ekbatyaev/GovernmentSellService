import logging
from datetime import  timezone
from time import sleep

from dateutil.relativedelta import relativedelta
from sqlalchemy import delete, func, select
from .connection_to_database import db_session
from .table_models import Purchase
from goszakupki_requests.data_request import get_docs_by_region, download_archive_from_result
from goszakupki_requests.parse_data_fz_223 import parse_zip_archive_purchases, parse_zip_archive_protocols
from .email_handles import send_email
from dotenv import load_dotenv
import os
import time as time_module
from datetime import datetime, timedelta, time
from typing import Dict, Any
import pandas as pd
import requests
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter


load_dotenv()

logger = logging.getLogger(__name__)

LOCK_KEY = int(os.getenv("SCHEDULER_LOCK_KEY", "424242"))

RETRY_COUNT = int(os.getenv("RETRY_COUNT"))
RETRY_DELAY =  int(os.getenv("RETRY_DELAY"))
BACKFILL_DAYS = int(os.getenv("BACKFILL_DAYS", "10"))
BACKFILL_ON_STARTUP = os.getenv("PIPELINE_BACKFILL_ON_STARTUP", "true").lower() == "true"

APP_URL = os.getenv("APP_URL")
API_BASE = os.getenv("API_BASE")
TOKEN = os.getenv("SYSTEM_TOKEN")

if not TOKEN:
    raise RuntimeError("SYSTEM_TOKEN is required")

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(threadName)s | %(name)s | %(message)s"
)


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

def put_purchase_to_db(purchase: dict) -> str:
    purchase_payload = dict(purchase)
    purchase_payload["token"] = TOKEN
    registration_number = purchase_payload.get("registration_number")
    guid = purchase_payload.get("guid")

    try:
        response = requests.post(
            f"{APP_URL}{API_BASE}/put_purchase",
            json=purchase_payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.exception(
            "Pipeline: ошибка запроса к API | reg=%s | guid=%s | error=%s",
            registration_number,
            guid,
            e,
        )
        return "skipped"
    except ValueError:
        logger.warning(
            "Pipeline: API вернул некорректный JSON | reg=%s | guid=%s",
            registration_number,
            guid,
        )
        return "skipped"

    message = data.get("message")

    if message == "Purchase updated":
        logger.info(
            "Pipeline: обновлена закупка через API | reg=%s | guid=%s",
            registration_number,
            guid,
        )
        return "updated"

    if message == "Purchase created":
        logger.info(
            "Pipeline: создана новая закупка через API | reg=%s | guid=%s",
            registration_number,
            guid,
        )
        return "created"

    logger.warning(
        "Pipeline: неизвестный ответ API | reg=%s | guid=%s | message=%s",
        registration_number,
        guid,
        message,
    )
    return "skipped"

def get_last_status() -> Dict[str, Any]:
    return LAST_JOB_STATUS


def delete_expired(db) -> int:
    today = _utcnow().date()

    stmt = (
        delete(Purchase)
        .where(Purchase.submission_close_datetime.isnot(None))
        .where(func.date(Purchase.submission_close_datetime) < today)
    )

    res = db.execute(stmt)
    return res.rowcount or 0


def process_day(date_str: str) -> Dict[str, int]:
    logger.info("Pipeline: обработка даты %s", date_str)

    result_purchases = get_docs_by_region(
        org_region="77",
        document_type="purchaseNotice",
        exact_date=date_str,
        subsystem_type="RI223",
    )

    added_registration_numbers = []

    created = 0
    updated = 0
    skipped = 0

    archive_urls_purchases = result_purchases.get("archive_urls", [])
    for archive_url in archive_urls_purchases:
        zip_path_purchases = download_archive_from_result(archive_url)

        logger.info("Pipeline: архив закупок скачан: %s", zip_path_purchases)

        purchases = parse_zip_archive_purchases(zip_path_purchases)

        logger.info("Pipeline: после фильтров закупок: %s", len(purchases))

        for p in purchases:
            try:
                status = put_purchase_to_db(p)
                added_registration_numbers.append(p["registration_number"])

                if status == "created":
                    created += 1
                elif status == "updated":
                    updated += 1
                else:
                    skipped += 1

            except Exception:
                logger.exception(
                    "Pipeline: ошибка сохранения закупки | reg=%s | guid=%s",
                    p.get("registration_number"),
                    p.get("guid"),
                )
                skipped += 1

    result_protocols = get_docs_by_region(
        org_region="77",
        document_type="purchaseProtocol",
        exact_date=date_str,
        subsystem_type="RI223",
    )

    archive_urls_protocols = result_protocols.get("archive_urls", [])

    for archive_url in archive_urls_protocols:
        zip_path_protocols = download_archive_from_result(archive_url)

        logger.info("Pipeline: архив протоколов скачан: %s", zip_path_protocols)

        protocols = parse_zip_archive_protocols(zip_path_protocols)

        logger.info("Pipeline: после фильтров протоколов: %s", len(protocols))

        for protocol in protocols:
            added_registration_numbers.append(protocol["registration_number"])

            try:
                response = requests.post(
                    f"{APP_URL}{API_BASE}/update_purchase",
                    json={
                        "token": TOKEN,
                        "registration_number": protocol["registration_number"],
                        "result_info": protocol["result_info"],
                        "documents_list": protocol["documents_list"],
                        "publication_datetime": protocol["publication_datetime"],
                    },
                    timeout=30,
                )
                response.raise_for_status()

                database_answer = response.json()

                if database_answer.get("message") == "Purchase not found" and not database_answer.get("data"):

                    status = put_purchase_to_db(protocol)

                    if status == "created":
                        created += 1

                    logger.info("Create purchase from protocol response | %s", response.text)

                    logger.info(
                        "Pipeline: протокол создал закупку | reg=%s",
                        protocol["registration_number"],
                    )

                    continue

                updated += 1

                logger.info("Update response | %s", response.text)

                logger.info(
                    "Pipeline: протокол обновил закупку | reg=%s",
                    protocol["registration_number"],
                )

            except Exception as error:
                logger.exception(
                    "У заявки не обновились поля | reg=%s | error=%s",
                    protocol.get("registration_number"),
                    error,
                )

    added_registration_numbers = list(set(added_registration_numbers))

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "added_registration_numbers": added_registration_numbers,
    }

def run_daily_job() -> Dict[str, Any]:
    _set_status(
        running=True,
        job="daily",
        started_at=_utcnow().isoformat(),
        finished_at=None,
        message="running",
        progress=None,
        result=None,
    )

    try:
        yesterday = (_utcnow() - timedelta(days=1)).date()
        date_str = yesterday.strftime("%Y-%m-%d")

        _set_status(progress={"date": date_str})

        max_attempts = 3
        retry_delay_sec = 10
        day_result = None

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    "Scheduler: daily attempt %s/%s for date %s",
                    attempt,
                    max_attempts,
                    date_str,
                )
                day_result = process_day(date_str)
                break
            except Exception as e:
                logger.warning(
                    "Scheduler: daily error (%s) attempt %s/%s: %s",
                    date_str,
                    attempt,
                    max_attempts,
                    e,
                )
                if attempt == max_attempts:
                    raise
                time_module.sleep(retry_delay_sec)

        if day_result is None:
            raise RuntimeError("Daily job finished without result")

        created = day_result["created"]
        updated = day_result["updated"]
        skipped = day_result["skipped"]
        added_registration_numbers = day_result["added_registration_numbers"]

        now = datetime.now()

        # Получение старых заявок и их удаление

        delete_date_to = now - relativedelta(years=1)

        purchases_response = requests.post(
            f"{APP_URL}{API_BASE}/get_all_purchases",
            json={"token": TOKEN,
                  "publication_datetime_to": delete_date_to.replace(microsecond=0).isoformat()},
            timeout=30,
        )

        purchases_response.raise_for_status()
        purchases = purchases_response.json().get("data", [])

        count = 0
        for purchase in purchases:
            try:
                delete_response = requests.post(
                    f"{APP_URL}{API_BASE}/delete_purchase",
                    json={"token": TOKEN, "guid": purchase["guid"]},
                    timeout=30,
                )

                count += 1

                delete_response.raise_for_status()
            except Exception as e:
                logger.info(
                    f"При удалении {purchase["guid"]}, произошла ошибка {e}",
                )
                continue

        logger.info(
            f"Daily job: успешно удалено {count} заявок"
        )

        emails_response = requests.post(
            f"{APP_URL}{API_BASE}/get_all_newsletters",
            json={"token": TOKEN},
            timeout=30,
        )
        emails_response.raise_for_status()
        emails = emails_response.json().get("data", [])

        html_content = f"""
                <html><body style="font-family:Arial;">
                <h2 style="color:#2E86C1;">Уведомление о заявках с госзакупок</h2>
                <p>Новых заявок добавлено: <b style="color:#E74C3C;font-size:18px;">{created}</b></p>
                <p>Заявок обновлено: <b style="color:#F39C12;font-size:18px;">{updated}</b></p>
                <p>Пропущено: <b style="color:#7F8C8D;font-size:18px;">{skipped}</b></p>
                <hr><p style="color:#888;font-size:12px;">Это письмо сформировано автоматически, отвечать на него не нужно</p>
                </body></html>
                """

        rows = []

        for registration_number in added_registration_numbers:
            purchase_response = requests.post(
                f"{APP_URL}{API_BASE}/get_purchase",
                json={"token": TOKEN, "registration_number": registration_number},
                timeout=30,
            )

            purchase_response.raise_for_status()

            purchase = purchase_response.json().get("data", {})

            customer = purchase.get("customer") or {}
            result_info = purchase.get("result_info") or {}

            base = {
                "Реестровый номер": purchase.get("registration_number"),
                "Название закупки": purchase.get("name"),
                "Сумма закупки": purchase.get("initial_sum"),
                "Дата начала подачи заявок": purchase.get("submission_start_datetime"),
                "Дата окончания подачи заявок": purchase.get("submission_close_datetime"),
                "Дата публикации": purchase.get("publication_datetime"),
                "Заказчик название": customer.get("full_name"),
                "Победитель": result_info.get("Победитель"),
                "Другие участники": result_info.get("Другие участники"),
                "Ячейки": result_info.get("Ячейки"),
                "Кол-во ячеек": result_info.get("Кол-во ячеек"),
                "Типовой проект": result_info.get("Типовой проект"),
                "Проектировщик": result_info.get("Проектировщик"),
                "Дата исполнения договора": result_info.get("Дата исполнения договора"),
                "Филиал/РЭС": result_info.get("Филиал/РЭС")
            }

            rows.append(base)

        result = {
            "ok": True,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "date": date_str,
        }

        analysis_path = "analysis.xlsx"

        try:
            df = pd.DataFrame(rows)
            df.to_excel(analysis_path, index=False)

            wb = load_workbook(analysis_path)
            ws = wb.active

            header_fill = PatternFill("solid", fgColor="366092")
            header_font = Font(color="FFFFFF", bold=True)
            cell_font = Font(size=10)
            align = Alignment(wrap_text=True, vertical="center")
            thin_side = Side(style="thin")
            border = Border(
                left=thin_side,
                right=thin_side,
                top=thin_side,
                bottom=thin_side,
            )

            for col in range(1, ws.max_column + 1):
                c = ws.cell(1, col)
                c.font = header_font
                c.fill = header_fill
                c.alignment = align
                c.border = border

            for r in range(2, ws.max_row + 1):
                ws.row_dimensions[r].height = 30
                for c in range(1, ws.max_column + 1):
                    cell = ws.cell(r, c)
                    cell.font = cell_font
                    cell.alignment = align
                    cell.border = border

            for col in range(1, ws.max_column + 1):
                letter = get_column_letter(col)
                max_len = max(
                    len(str(ws.cell(r, col).value or ""))
                    for r in range(1, ws.max_row + 1)
                )
                ws.column_dimensions[letter].width = min(max_len + 2, 50)

            last = ws.max_row + 2
            ws.cell(last, 1, "Сноска: данные по закупкам, лотам и позициям")
            ws.merge_cells(
                start_row=last,
                start_column=1,
                end_row=last,
                end_column=ws.max_column,
            )

            footnote_cell = ws.cell(last, 1)
            footnote_cell.font = Font(italic=True, size=9, color="555555")
            footnote_cell.alignment = Alignment(horizontal="center")
            footnote_cell.border = Border(top=Side(style="thin", color="AAAAAA"))

            wb.save(analysis_path)

            subject = f"Заявки с госзакупок за {now.strftime('%d.%m.%Y')}"

            for u in emails:
                email = u.get("email")
                if not email:
                    continue

                send_email(
                    email,
                    subject,
                    html_content,
                    attachments=[analysis_path] if (created or updated) else None,
                )

        finally:
            if os.path.exists(analysis_path):
                os.remove(analysis_path)

        _set_status(
            running=False,
            finished_at=_utcnow().isoformat(),
            message="done",
            result=result,
        )
        logger.info("Scheduler: daily done | %s", result)
        return result

    except Exception as e:
        logger.exception("Scheduler: daily job failed")
        error_result = {"ok": False, "error": str(e)}

        _set_status(
            running=False,
            finished_at=_utcnow().isoformat(),
            message=f"error: {e}",
            result=error_result,
        )
        return error_result


def run_backfill(days: int | None = None) -> Dict[str, Any]:
    days = int(days or BACKFILL_DAYS)
    _set_status(
        running=True,
        job="backfill",
        started_at=_utcnow().isoformat(),
        finished_at=None,
        message="running",
        progress={"days": days, "current": 0, "date": None, "created_total": 0, "updated_total": 0},
        result=None,
    )

    created_total = 0
    updated_total = 0
    skipped_total = 0
    processed_days = 0
    failed_days = []

    try:
        today = _utcnow().date()
        start = today - timedelta(days=days)

        for i in range(days):
            d = start + timedelta(days=i)
            if d >= today:
                continue

            date_str = d.strftime("%Y-%m-%d")
            processed_days += 1

            _set_status(progress={
                "days": days,
                "current": i + 1,
                "date": date_str,
                "created_total": created_total,
                "updated_total": updated_total,
                "skipped_total": skipped_total,
            })

            logger.info("Backfill: day %s/%s | %s", i + 1, days, date_str)

            success = False
            for attempt in range(RETRY_COUNT):
                try:
                    day_result = process_day(date_str)
                    created_total += day_result["created"]
                    updated_total += day_result["updated"]
                    skipped_total += day_result["skipped"]
                    success = True
                    break
                except Exception as e:
                    logger.warning(
                        "Backfill error (%s) attempt %s/%s: %s",
                        date_str, attempt + 1, RETRY_COUNT, e
                    )
                    sleep(RETRY_DELAY)

            if not success:
                logger.error("Backfill: пропускаю дату %s после %s попыток", date_str, RETRY_COUNT)
                failed_days.append(date_str)

        result = {
            "ok": True,
            "processed_days": processed_days,
            "created_total": created_total,
            "updated_total": updated_total,
            "skipped_total": skipped_total,
            "failed_days": failed_days,
        }

        _set_status(
            running=False,
            finished_at=_utcnow().isoformat(),
            message="done",
            result=result
        )

        logger.info("Scheduler(backfill): done | %s", result)
        return result

    except Exception as e:
        logger.exception("Scheduler(backfill) failed")
        _set_status(
            running=False,
            finished_at=_utcnow().isoformat(),
            message=f"error: {e}",
            result={"ok": False, "error": str(e)}
        )
        return {"ok": False, "error": str(e)}


def run_backfill_on_startup() -> None:
    if not BACKFILL_ON_STARTUP:
        logger.info("Backfill on startup disabled")
        return
    run_backfill(BACKFILL_DAYS)