import asyncio
from dateutil.relativedelta import relativedelta
from datetime import timedelta
from app.backend.database.crud.purchase import search_purchases
from app.settings import logger, settings
from app.backend.functions.notices.process import process_day
from app.backend.functions.analysis import send_analysis
from app.backend.constraints import REGIONS_OF_THE_FILTERS, REGION_CODES_BY_FEDERAL_DISTRICT
from app.backend.scheduler.functions import moscow_datetime, clean_notices, clean_auth_codes, complete_row_tender
from app.backend.database.settings import db_session
from app.backend.scheduler.schemas import ResultDailyTask
from app.backend.database.crud.newsletter import search_newsletters
from app.schemas.newsletter import FilterNewsLetters
from app.schemas.purchase import Notice, FilterNotice
from sqlalchemy.exc import IntegrityError


async def daily_task() -> ResultDailyTask:
    logger.info(f"Daily job started at {moscow_datetime().strftime("%d.%m.%Y %H:%M:%S")}")

    yesterday = (moscow_datetime() - timedelta(days=1)).date()
    date_string = yesterday.strftime("%Y-%m-%d")

    result = ResultDailyTask(
        status=True,
        created=0,
        updated=0,
        skipped=0,
        date=date_string
    )

    try:

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

        publication_datetime_to = moscow_datetime() - relativedelta(months=6)

        async with db_session() as db:
            await clean_notices(db=db, publication_datetime_to=publication_datetime_to)

        # Удаление истекших кодов подтверждения

        created_at_to = moscow_datetime() - relativedelta(minutes=5)

        async with db_session() as db:
            await clean_auth_codes(db=db, created_at_to=created_at_to)

        # Рассылка сообщений адрессантам

        # Высылаем информацию по Россетям

        filter_name = "Тендеры для Россетей"

        for district_name in REGIONS_OF_THE_FILTERS[filter_name]:

            group = day_result[filter_name][district_name]
            created, updated, skipped = len(group.created), len(group.updated), len(group.skipped)
            registration_numbers = group.created + group.updated + group.skipped
            async with db_session() as db:
                try:
                    newsletters = await search_newsletters(db, FilterNewsLetters(list_filter_type_names=[filter_name],
                                                                            list_district_names=[district_name]))
                    emails = [n.email for n in newsletters]
                except IntegrityError as e:
                    logger.exception(f"Произошла ошибка получения данных подписантов: {e}")
                    raise

            if not emails:
                logger.info(f"Подписантов на {filter_name}, {district_name} нет.")
                continue

            rows = []

            for registration_number in registration_numbers:

                async with db_session() as db:
                    try:
                        purchases = await search_purchases(db, FilterNotice(registration_number=registration_number,
                                                                                list_filter_type_name=[filter_name]))
                    except IntegrityError as e:
                        logger.exception(f"Произошла ошибка получения данных поиска заявок: {e}, ")
                        raise

                if not purchases:
                    logger.warning(f"Заявка под регистрационным номером: {registration_number} и фильтром: {filter_name} не найдена.")
                    continue

                purchase: Notice = purchases[0]
                rows.append(await complete_row_tender(filter_name, purchase))

            result.created += created
            result.updated += updated
            result.skipped += skipped

            extra_rows = []

            extra_purchases: list[Notice] = []

            async with db_session() as db:
                try:
                    extra_purchases = await search_purchases(db, FilterNotice(list_filter_type_name=[filter_name],
                                                                        region_numbers=[district_name]))
                except IntegrityError as e:
                    logger.exception(f"Произошла ошибка получения данных поиска заявок: {e}, ")
                    raise

            if not extra_purchases:
                logger.warning(
                    f"Заявки с фильтрами: {filter_name}, {district_name} не найдены.")

            for purchase in extra_purchases:
                extra_rows.append(await complete_row_tender(filter_name, purchase))

            await send_analysis(date_of_processing_notices=yesterday, rows=rows, emails=emails,
                            created=created, updated=updated, skipped=skipped, extra_rows=extra_rows)


        # Высылаем информацию для OEM

        filter_name = "Тендеры для OEM"

        for district_name in REGION_CODES_BY_FEDERAL_DISTRICT.keys():

            created = 0
            updated = 0
            skipped = 0

            registration_numbers = []

            for region in REGION_CODES_BY_FEDERAL_DISTRICT[district_name]:
                created += len(day_result[filter_name][region].created)
                updated += len(day_result[filter_name][region].updated)
                skipped += len(day_result[filter_name][region].skipped)

                registration_numbers += (day_result[filter_name][region].created +
                                         day_result[filter_name][region].updated +
                                         day_result[filter_name][region].skipped)

            async with db_session() as db:
                try:
                    newsletters = await search_newsletters(db, FilterNewsLetters(list_filter_type_names=[filter_name],
                                                                            list_district_names=[district_name]))
                    emails = [n.email for n in newsletters]
                except IntegrityError as e:
                    logger.exception(f"Произошла ошибка получения данных подписантов: {e}")
                    raise

            if not emails:
                logger.info(f"Подписантов на {filter_name}, {district_name} нет.")
                continue

            rows = []

            for registration_number in registration_numbers:

                async with db_session() as db:
                    try:
                        purchases = await search_purchases(db, FilterNotice(registration_number=registration_number,
                                                                                list_filter_type_name=[filter_name]))
                    except IntegrityError as e:
                        logger.exception(f"Произошла ошибка получения данных поиска заявок: {e}, ")
                        raise

                if not purchases:
                    logger.warning(f"Заявка под регистрационным номером: {registration_number} и фильтром: {filter_name} не найдена.")
                    continue

                purchase: Notice = purchases[0]

                rows.append(await complete_row_tender(filter_name, purchase))

            result.created += created
            result.updated += updated
            result.skipped += skipped

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
                created += len(day_result[filter_name][region].created)
                updated += len(day_result[filter_name][region].updated)
                skipped += len(day_result[filter_name][region].skipped)

                registration_numbers += (day_result[filter_name][region].created +
                                         day_result[filter_name][region].updated +
                                         day_result[filter_name][region].skipped)

            async with db_session() as db:
                try:
                    newsletters = await search_newsletters(db, FilterNewsLetters(list_filter_type_names=[filter_name],
                                                                            list_district_names=[district_name]))
                    emails = [n.email for n in newsletters]
                except IntegrityError as e:
                    logger.exception(f"Произошла ошибка получения данных подписантов: {e}")
                    raise

            if not emails:
                logger.info(f"Подписантов на {filter_name}, {district_name} нет.")
                continue

            rows = []

            for registration_number in registration_numbers:

                async with db_session() as db:
                    try:
                        purchases = await search_purchases(db, FilterNotice(registration_number=registration_number,
                                                                                list_filter_type_name=[filter_name]))
                    except IntegrityError as e:
                        logger.exception(f"Произошла ошибка получения данных поиска заявок: {e}, ")
                        raise

                if not purchases:
                    logger.warning(f"Заявка под регистрационным номером: {registration_number} и фильтром: {filter_name} не найдена.")
                    continue

                purchase: Notice = purchases[0]

                rows.append(await complete_row_tender(filter_name, purchase))

            result.created += created
            result.updated += updated
            result.skipped += skipped

            await send_analysis(date_of_processing_notices = yesterday, rows=rows, emails=emails,
                            created=created, updated=updated, skipped=skipped)

        logger.info(f"Scheduler: daily done at {str(moscow_datetime().isoformat())} with result: {result.model_dump()}")

    except Exception as e:
        logger.exception(f"Scheduler: daily job failed at {str(moscow_datetime().isoformat())}, error: {e}")
        result.status = False

    return result