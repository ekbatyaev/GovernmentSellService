import asyncio
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from typing import Dict, Any
from app.settings import logger, settings
from app.backend.functions import process_day, api_datum_query, send_analysis
from app.backend.db.static_info import REGIONS_OF_THE_FILTERS, REGION_CODES_BY_FEDERAL_DISTRICT

scheduler: AsyncIOScheduler | None = None

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

async def create_scheduler() -> AsyncIOScheduler:
    s = AsyncIOScheduler(timezone = MOSCOW_TZ)
    s.add_job(
        run_daily_job,
        trigger=CronTrigger(hour=settings.daily_job_hour_msk,
                            minute=settings.daily_job_minute_msk, timezone=MOSCOW_TZ),
        id="daily_pipeline",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    return s

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

def moscow_datetime() -> datetime:
    return datetime.now(MOSCOW_TZ)


async def run_daily_job() -> Dict[str, Any]:

    logger.info(f"Daily job started at{moscow_datetime().isoformat()}")
    try:
        yesterday = (moscow_datetime() - timedelta(days=1)).date()
        date_string = yesterday.strftime("%Y-%m-%d")

        logger.info(f"Processing date: {date_string}")

        day_result = None

        for attempt in range(1, settings.retry_count + 1):
            try:
                logger.info(
                    "Scheduler: daily attempt %s/%s for date %s",
                    attempt,
                    settings.retry_count,
                    date_string,
                )
                day_result = await process_day(date_string, 0)
                break
            except Exception as e:
                logger.warning(
                    "Scheduler: daily error (%s) attempt %s/%s: %s",
                    date_string,
                    attempt,
                    settings.retry_count,
                    e,
                )
                if attempt == settings.retry_count:
                    raise
                await asyncio.sleep(settings.retry_delay)

        if day_result is None:
            raise RuntimeError("Daily job finished without result")


        now = moscow_datetime()

        # Получение старых заявок и их удаление

        delete_date_to = now - relativedelta(years=1)

        purchases = await api_datum_query(token=settings.token,
                                              endpoint="get_all_purchases",
                                              publication_datetime_to = delete_date_to.replace(microsecond=0).isoformat())

        count = 0
        for purchase in purchases:
            try:
                await api_datum_query(token=settings.token,
                                              endpoint="delete_purchase",
                                              guid = purchase["guid"])
                count += 1
            except Exception as e:
                logger.info(
                    f"При удалении {purchase["guid"]}, произошла ошибка {e}",
                )
                continue

        logger.info(
            f"Daily job: успешно удалено {count} заявок"
        )

        # Рассылка сообщений адрессантам

        # Высылаем информацию по Россетям

        result = {
            "ok": True,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "date": date_string,
        }

        filter_name = "Тендеры для Россетей"

        for district_name in REGIONS_OF_THE_FILTERS[filter_name]:

            created = 0
            updated = 0
            skipped = 0

            registration_numbers = []


            for region in day_result[filter_name].keys():
                created += len(day_result[filter_name][region]["created"])
                updated += len(day_result[filter_name][region]["updated"])
                skipped += len(day_result[filter_name][region]["skipped"])

                registration_numbers += (day_result[filter_name][region]["created"] +
                                         day_result[filter_name][region]["updated"] +
                                         day_result[filter_name][region]["skipped"])

            emails = await api_datum_query(token=settings.token,
                                  endpoint="get_all_newsletters",
                                  filter_type_name = filter_name, district_name = district_name)
            rows = []

            for registration_number in registration_numbers:

                purchase = await api_datum_query(token=settings.token,
                                               endpoint="get_purchase",
                                               registration_number = registration_number, filter_type_name = filter_name)

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
                    "Филиал/РЭС": result_info.get("Филиал/РЭС"),
                    "Ссылка на тендер": f"https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber={purchase.get("registration_number")}"
                }

                rows.append(base)

            result["created"] += created
            result["updated"] += updated
            result["skipped"] += skipped

            extra_rows = []

            purchases = await api_datum_query(token=settings.token,
                                              endpoint="get_all_purchases",
                                              filter_type_name = filter_name, region_number = district_name)

            for purchase in purchases:

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
                    "Филиал/РЭС": result_info.get("Филиал/РЭС"),
                    "Ссылка на тендер": f"https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber={purchase.get("registration_number")}"
                }

                extra_rows.append(base)


            await send_analysis(rows=rows, emails=emails,
                            created=created, updated=updated, skipped=skipped, extra_rows = extra_rows)


        # Высылаем информацию для OEM

        filter_name = "Тендеры для OEM"

        for district_name in REGION_CODES_BY_FEDERAL_DISTRICT.keys():

            created = 0
            updated = 0
            skipped = 0

            registration_numbers = []

            for region in REGION_CODES_BY_FEDERAL_DISTRICT[district_name]:
                created += len(day_result[filter_name][region]["created"])
                updated += len(day_result[filter_name][region]["updated"])
                skipped += len(day_result[filter_name][region]["skipped"])

                registration_numbers += (day_result[filter_name][region]["created"] +
                                         day_result[filter_name][region]["updated"] +
                                         day_result[filter_name][region]["skipped"])

            emails = await api_datum_query(token=settings.token,
                                           endpoint="get_all_newsletters",
                                           filter_type_name=filter_name, district_name=district_name)

            rows = []

            for registration_number in registration_numbers:

                purchase = await api_datum_query(token=settings.token,
                                               endpoint="get_purchase",
                                               registration_number = registration_number, filter_type_name = filter_name)

                customer = purchase.get("customer") or {}

                result_info = purchase.get("result_info") or {}

                contact = purchase.get("contact") or {}


                base = {
                    "Реестровый номер": purchase.get("registration_number"),
                    "Название закупки": purchase.get("name"),
                    "Сумма закупки": purchase.get("initial_sum"),
                    "Дата начала подачи заявок": purchase.get("submission_start_datetime"),
                    "Дата окончания подачи заявок": purchase.get("submission_close_datetime"),
                    "Дата публикации": purchase.get("publication_datetime"),
                    "Заказчик название": customer.get("full_name"),
                    "Контактное лицо": (contact.get("last_name") or "")+ " " + (contact.get("first_name") or "") + " " + (contact.get("middle_name") or ""),
                    "Телефон": (contact.get("phone") or ""),
                    "Email": (contact.get("email") or ""),
                    "Победитель": result_info.get("Победитель"),
                    "Итоговая цена контракта": result_info.get("Итоговая цена контракта"),
                    "Слова маячки в тз": result_info.get("Слова маячки в тз"),
                    "Ссылка на тендер": f"https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber={purchase.get("registration_number")}"
                }

                rows.append(base)

            result["created"] += created
            result["updated"] += updated
            result["skipped"] += skipped

            await send_analysis(rows=rows, emails=emails,
                            created=created, updated=updated, skipped=skipped)

        # Высылаем информацию для ITM

        filter_name = "Тендеры для ITM"

        for district_name in REGION_CODES_BY_FEDERAL_DISTRICT.keys():

            created = 0
            updated = 0
            skipped = 0

            registration_numbers = []

            for region in REGION_CODES_BY_FEDERAL_DISTRICT[district_name]:
                created += len(day_result[filter_name][region]["created"])
                updated += len(day_result[filter_name][region]["updated"])
                skipped += len(day_result[filter_name][region]["skipped"])

                registration_numbers += (day_result[filter_name][region]["created"] +
                                         day_result[filter_name][region]["updated"] +
                                         day_result[filter_name][region]["skipped"])

            emails = await api_datum_query(token=settings.token,
                                           endpoint="get_all_newsletters",
                                           filter_type_name=filter_name, district_name=district_name)

            rows = []

            for registration_number in registration_numbers:

                purchase = await api_datum_query(token=settings.token,
                                                 endpoint="get_purchase",
                                                 registration_number=registration_number, filter_type_name=filter_name)

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
                    "ИНН": result_info.get("ИНН"),
                    "Итоговая цена контракта": result_info.get("Итоговая цена контракта"),
                    "Другие участники": result_info.get("Другие участники"),
                    "Ссылка на тендер": f"https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber={purchase.get("registration_number")}"
                }

                rows.append(base)

            result["created"] += created
            result["updated"] += updated
            result["skipped"] += skipped

            await send_analysis(rows=rows, emails=emails,
                            created=created, updated=updated, skipped=skipped)

        logger.info(f"Scheduler: daily done at {str(moscow_datetime().isoformat())} with result: {result}")
        return result

    except Exception as e:
        logger.exception(f"Scheduler: daily job failed at {str(moscow_datetime().isoformat())}")
        error_result = {"ok": False, "error": str(e)}
        return error_result


async def run_backfill(days: int | None = None, filter_number = 0) -> Dict[str, Any]:
    days = int(days or settings.backfill_days)

    logger.info(f"Backfill with {days} days period has started at {str(moscow_datetime().isoformat())}")

    created_total = 0
    updated_total = 0
    skipped_total = 0
    processed_days = 0
    failed_days = []

    try:
        today = moscow_datetime().date()
        start = today - timedelta(days=days)

        for i in range(days):
            d = start + timedelta(days=i)
            if d >= today:
                continue

            date_string = d.strftime("%Y-%m-%d")
            processed_days += 1

            logger.info(f"Backfill: day {i + 1}/{days} | {date_string}, "
                        f"created_total: {created_total}, updated_total: {updated_total}, skipped_total: {skipped_total}")

            success = False
            for attempt in range(settings.retry_count):
                try:
                    day_result = await process_day(date_string, filter_number)
                    for filter_name in REGIONS_OF_THE_FILTERS:

                        for region in day_result[filter_name].keys():
                            created_total += len(day_result[filter_name][region]["created"])
                            updated_total += len(day_result[filter_name][region]["updated"])
                            skipped_total += len(day_result[filter_name][region]["skipped"])

                    success = True
                    break
                except Exception as e:
                    logger.warning(
                        "Backfill error (%s) attempt %s/%s: %s",
                        date_string, attempt + 1, settings.retry_count, e
                    )
                    await asyncio.sleep(settings.retry_delay)

            if not success:
                logger.error("Backfill: пропускаю дату %s после %s попыток", date_string, settings.retry_count)
                failed_days.append(date_string)

        result = {
            "ok": True,
            "processed_days": processed_days,
            "created_total": created_total,
            "updated_total": updated_total,
            "skipped_total": skipped_total,
            "failed_days": failed_days,
        }

        logger.info(f"Scheduler(backfill): done at "
                    f"{str(moscow_datetime().isoformat())} with result: {result}")
        return result

    except Exception as e:
        logger.exception(f"Scheduler(backfill) failed at {str(moscow_datetime().isoformat())}")
        return {"ok": False, "error": str(e)}