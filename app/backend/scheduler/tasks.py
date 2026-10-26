import asyncio
from dateutil.relativedelta import relativedelta
from datetime import timedelta
from typing import Dict, Any, List
from app.settings import logger, settings
from app.backend.functions.functions import process_day, send_analysis
from app.backend.database.static_info import REGIONS_OF_THE_FILTERS, REGION_CODES_BY_FEDERAL_DISTRICT
from app.backend.scheduler.functions import moscow_datetime, clean_old_notices, clean_old_auth_codes
from app.backend.database.settings import db_session


async def daily_task() -> Dict[str, Any]:
    logger.info(f"Daily job started at {moscow_datetime().strftime("%d.%m.%Y %H:%M:%S")}")
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

        # Удаление старых заявок из базы данных

        delete_date_to = moscow_datetime() - relativedelta(months=6)

        async with db_session() as db:
            await clean_old_notices(db=db, delete_date_to=delete_date_to)

        # Удаление истекших кодов подтверждения

        delete_date_to = now - relativedelta(months=6)

        api_response = await api_datum_query(token=settings.system_token,
                                             endpoint="get_all_purchases",
                                             publication_datetime_to=delete_date_to.replace(microsecond=0).isoformat())

        purchases: List = api_response.get("data") or []

        count = 0
        for purchase in purchases:
            api_response = await api_datum_query(token=settings.system_token,
                                                 endpoint="delete_purchase",
                                                 guid=purchase["guid"])

            if api_response == {}:
                logger.info(
                    f"При удалении {purchase["guid"]}, произошла ошибка",
                )
                continue

            count += 1
        logger.info(
            f"Daily job: успешно удалено {count} заявок из {len(purchases)}"
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

            api_response = await api_datum_query(token=settings.system_token,
                                  endpoint="get_all_newsletters",
                                  filter_type_name = filter_name, district_name = district_name)

            emails: List = api_response.get("data") or []
            rows = []

            for registration_number in registration_numbers:

                api_response = await api_datum_query(token=settings.system_token,
                                               endpoint="get_purchase",
                                               registration_number = registration_number, filter_type_name = filter_name)

                purchase: Dict = api_response.get("data") or {}

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

            api_response = await api_datum_query(token=settings.system_token,
                                              endpoint="get_all_purchases",
                                              filter_type_name = filter_name, region_number = district_name)

            purchases = api_response.get("data") or []

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


            await send_analysis(date_of_processing_notices = yesterday, rows=rows, emails=emails,
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

            api_response = await api_datum_query(token=settings.system_token,
                                           endpoint="get_all_newsletters",
                                           filter_type_name=filter_name, district_name=district_name)
            emails: List = api_response.get("data") or []

            rows = []

            for registration_number in registration_numbers:

                api_response = await api_datum_query(token=settings.system_token,
                                               endpoint="get_purchase",
                                               registration_number = registration_number, filter_type_name = filter_name)

                purchase: Dict = api_response.get("data") or {}

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
                    "Контактное лицо": (contact.get("last_name") or "") + " " + (contact.get("first_name") or "") + " " + (contact.get("middle_name") or ""),
                    "Телефон": (contact.get("phone") or ""),
                    "Email": (contact.get("newsletters") or ""),
                    "Победитель": result_info.get("Победитель"),
                    "Итоговая цена контракта": result_info.get("Итоговая цена контракта"),
                    "Слова маячки в тз": result_info.get("Слова маячки в тз"),
                    "Ссылка на тендер": f"https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber={purchase.get("registration_number")}"
                }

                rows.append(base)

            result["created"] += created
            result["updated"] += updated
            result["skipped"] += skipped

            await send_analysis(date_of_processing_notices = yesterday, rows=rows, emails=emails,
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

            api_response = await api_datum_query(token=settings.system_token,
                                           endpoint="get_all_newsletters",
                                           filter_type_name=filter_name, district_name=district_name)

            emails: List = api_response.get("data") or []

            rows = []

            for registration_number in registration_numbers:

                api_response = await api_datum_query(token=settings.system_token,
                                                 endpoint="get_purchase",
                                                 registration_number=registration_number, filter_type_name=filter_name)

                purchase: Dict = api_response.get("data") or {}

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

            await send_analysis(date_of_processing_notices = yesterday, rows=rows, emails=emails,
                            created=created, updated=updated, skipped=skipped)

        logger.info(f"Scheduler: daily done at {str(moscow_datetime().isoformat())} with result: {result}")
        return result

    except Exception as e:
        logger.exception(f"Scheduler: daily job failed at {str(moscow_datetime().isoformat())}")
        error_result = {"ok": False, "error": str(e)}
        return error_result