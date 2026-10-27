from app.settings import logger, settings
from app.backend.constraints import REGIONS_OF_THE_FILTERS, ALL_REGION_CODES
from app.backend.parsers.request_archives import get_docs_by_region, download_archive_from_result
from app.backend.parsers.xml_parser import parse_zip_archive_purchases, parse_zip_archive_protocols
from app.backend.schemas import GroupsRegNumbers
from app.backend.functions.notices.record import save_purchase_record, save_protocol_record
from datetime import datetime, timedelta
import asyncio

async def _process_purchases_for_region(
    region,
    date_str: str,
    filter_number: int,
    registration_numbers_dict_per_day: dict,
    archive_semaphore: asyncio.Semaphore,
    record_semaphore: asyncio.Semaphore,
    attempts: int = 3
) -> None:
    result_purchases = {}

    for attempt in range(1, attempts + 1):
        try:
            result_purchases = await get_docs_by_region(
                org_region=region,
                document_type="purchaseNotice",
                exact_date=date_str,
                subsystem_type="RI223",
            )
            break
        except Exception:
            logger.exception(
                "Pipeline: не удалось получить список закупок | region=%s | попытка %s/%s",
                region, attempt, attempts,
            )
            if attempt == attempts:
                return
            await asyncio.sleep(attempt * 2)

    archive_urls_purchases = result_purchases.get("archive_urls", [])

    async def _handle_archive(archive_url: str) -> None:
        async with archive_semaphore:
            try:
                zip_path_purchases = await download_archive_from_result(archive_url)

                if zip_path_purchases is None:
                    logger.warning("Pipeline: скачивание архива закупок не удалось | region=%s | archive_url=%s", region, archive_url)
                    return

                logger.info("Pipeline: архив закупок скачан: %s", zip_path_purchases)

                purchases = await parse_zip_archive_purchases(zip_path_purchases, region, filter_number)

                logger.info("Pipeline: после фильтров закупок: %s", len(purchases))

                await asyncio.gather(*[
                    save_purchase_record(purchase, registration_numbers_dict_per_day, record_semaphore)
                    for purchase in purchases
                ])
            except Exception:
                logger.exception(
                    "Pipeline: ошибка обработки архива закупок | region=%s | archive_url=%s",
                    region,
                    archive_url,
                )

    await asyncio.gather(*[_handle_archive(url) for url in archive_urls_purchases])


async def _process_protocols_for_region(
    region,
    date_str: str,
    filter_number: int,
    registration_numbers_dict_per_day: dict,
    archive_semaphore: asyncio.Semaphore,
    record_semaphore: asyncio.Semaphore,
    attempts: int = 3
) -> None:
    result_protocols = {}

    for attempt in range(1, attempts + 1):
        try:
            result_protocols = await get_docs_by_region(
                org_region=region,
                document_type="purchaseProtocol",
                exact_date=date_str,
                subsystem_type="RI223",
            )
            break
        except Exception:
            logger.exception(
                "Pipeline: не удалось получить список закупок | region=%s | попытка %s/%s",
                region, attempt, attempts,
            )
            if attempt == attempts:
                return
            await asyncio.sleep(attempt * 2)

    archive_urls_protocols = result_protocols.get("archive_urls", [])

    async def _handle_archive(archive_url: str) -> None:
        async with archive_semaphore:
            try:
                zip_path_protocols = await download_archive_from_result(archive_url)

                if zip_path_protocols is None:
                    logger.info("Pipeline: скачивание архива не удалось")
                    return

                logger.info("Pipeline: архив протоколов скачан: %s", zip_path_protocols)

                protocols = await parse_zip_archive_protocols(zip_path_protocols, region, filter_number)

                logger.info("Pipeline: после фильтров протоколов: %s", len(protocols))

                await asyncio.gather(*[
                    save_protocol_record(protocol, registration_numbers_dict_per_day, record_semaphore)
                    for protocol in protocols
                ])
            except Exception:
                logger.exception(
                    "Pipeline: ошибка обработки архива протоколов | region=%s | archive_url=%s",
                    region,
                    archive_url,
                )

    await asyncio.gather(*[_handle_archive(url) for url in archive_urls_protocols])

async def process_day(date_str: str, filter_number=0) -> dict:
    logger.info("Pipeline: обработка даты %s", date_str)

    registration_numbers_dict_per_day = {}

    for filter_name in REGIONS_OF_THE_FILTERS.keys():
        registration_numbers_dict_per_day[filter_name] = {}
        for region_code in REGIONS_OF_THE_FILTERS[filter_name]:
            registration_numbers_dict_per_day[filter_name][region_code] = GroupsRegNumbers()

    region_semaphore = asyncio.Semaphore(settings.region_process_concurrency)
    archive_semaphore = asyncio.Semaphore(settings.archive_process_concurrency)
    record_semaphore = asyncio.Semaphore(settings.record_concurrency)

    async def _process_region(region) -> None:
        async with region_semaphore:
            try:
                # Закупки и протоколы одного региона не пересекаются по
                # данным — тянем параллельно.
                await asyncio.gather(
                    _process_purchases_for_region(
                        region, date_str, filter_number, registration_numbers_dict_per_day,
                        archive_semaphore, record_semaphore,
                    ),
                    _process_protocols_for_region(
                        region, date_str, filter_number, registration_numbers_dict_per_day,
                        archive_semaphore, record_semaphore,
                    ),
                )
            except Exception:
                logger.exception("Pipeline: не удалось обработать регион %s", region)

    await asyncio.gather(*[_process_region(region) for region in ALL_REGION_CODES])

    return registration_numbers_dict_per_day

async def process_period(date_from: datetime, date_to: datetime, filter_number: int):
    logger.info(
        "Processing period of time from %s to %s have started",
        date_from.strftime("%Y-%m-%d"),
        date_to.strftime("%Y-%m-%d"),
    )

    while date_from < date_to:
        await process_day(date_from.strftime("%Y-%m-%d"), filter_number=filter_number)
        date_from += timedelta(days=1)
