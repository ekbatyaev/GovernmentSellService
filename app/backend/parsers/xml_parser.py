import asyncio
import copy
import json
import os
import re
import uuid
import zipfile
from typing import Any, Dict, List, Optional, Tuple
import xmltodict
from app.backend.api_client import api_datum_query
from app.settings import settings, logger
from app.backend.parsers.filters.rosseti import request_filters_rosseti
from app.backend.parsers.filters.oem import request_filters_oem
from app.backend.parsers.filters.itm import request_filters_itm
from app.backend.parsers.doc_parser import process_attached_files_and_merge

# Регионы для фильтров
REGIONS_ROSSETI = {
    "77": True,  # Москва
    "12": True,  # Республика Марий Эл (Мариэнерго)
    "52": True,  # Нижегородская область (Нижновэнерго)
    "43": True,  # Кировская область (Кировэнерго)
    "56": True,  # Оренбургская область (Оренбургэнерго)
    "18": True,  # Удмуртская Республика (Удмуртэнерго)
    "36": True,  # Воронежская область (Воронежэнерго)
    "63": True,  # Самарская область (Самарские РС)
    "31": True,  # Белгородская область (Белгородэнерго)
    "57": True,  # Орловская область (Орелэнерго)
    "64": True,  # Саратовская область (Саратовские РС)
    "33": True,  # Владимирская область (Владимирэнерго)
    "37": True,  # Ивановская область (Ивэнерго)
    "62": True,  # Рязанская область (Рязаньэнерго)
    "71": True,  # Тульская область (Тулаэнерго)
    "44": True,  # Костромская область (Костромаэнерго)
    "76": True,  # Ярославская область (Ярэнерго)
    "69": True,  # Тверская область (Тверьэнерго)
    "67": True,  # Смоленская область (Смоленскэнерго)
    "32": True,  # Брянская область (Брянскэнерго)
    "46": True,  # Курская область (Курскэнерго)
    "48": True,  # Липецкая область (Липецкэнерго)
    "68": True,  # Тамбовская область (Тамбовэнерго)
    "40": True,  # Калужская область (Калугаэнерго)
}

FIELDS = [
    "Победитель",
    "Другие участники",
    "Ячейки",
    "Кол-во ячеек",
    "Типовой проект",
    "Проектировщик",
    "Дата исполнения договора",
    "Филиал/РЭС",
]

# Таймаут одного обращения к БД/API за карточкой закупки.
API_TIMEOUT_SECONDS = 30

MAX_CONCURRENT_FILES = 8


def _remove_ns(obj):
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            clean_key = k.split(":")[-1]
            new_dict[clean_key] = _remove_ns(v)
        return new_dict
    if isinstance(obj, list):
        return [_remove_ns(item) for item in obj]
    return obj


def _ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _extract_documents(attachments: dict) -> list:
    """Общая логика извлечения списка документов из attachments (раньше была
    продублирована по два раза в каждой из _normalize_* функций)."""
    document = (attachments or {}).get("document")
    if isinstance(document, str):
        try:
            document = json.loads(document)
        except Exception:
            document = None
    document = _ensure_list(document)
    return [
        {
            "filename": doc.get("fileName", ""),
            "description": doc.get("description", ""),
            "url": doc.get("url", ""),
        }
        for doc in document
    ]


def _normalize_protocol(data: dict) -> dict:

    body = (data.get("purchaseProtocol") or {}).get("body") or {}
    item = body.get("item", {}) or {}
    protocol = item.get("purchaseProtocolData", {}) or {}
    purchase_info = protocol.get("purchaseInfo", {}) or {}
    lots_protocol_info = (protocol.get("lotApplicationsList") or {}).get("protocolLotApplications") or {}

    result = {}

    result["registration_number"] = purchase_info.get("purchaseNoticeNumber")
    result["name"] = purchase_info.get("name")
    result["publication_datetime"] = protocol.get("publicationDateTime")
    result["submission_start_datetime"] = protocol.get("procedureDate", "")
    result["submission_close_datetime"] = protocol.get("procedureDate", "")

    customer = (protocol.get("customer") or {}).get("mainInfo") or {}
    result["customer"] = {
        "full_name": customer.get("fullName"),
        "inn": customer.get("inn"),
        "kpp": customer.get("kpp"),
        "ogrn": customer.get("ogrn"),
    }

    contact = protocol.get("contact") or {}
    result["contact"] = {
        "last_name": contact.get("lastName", ""),
        "first_name": contact.get("firstName", ""),
        "middle_name": contact.get("middleName", ""),
        "phone": contact.get("phone", ""),
        "email": contact.get("email", ""),
    }

    result["apply_request"] = {
        "submission_order": protocol.get("applSubmisionOrder", ""),
        "submission_place": protocol.get("applSubmisionPlace", "")
    }

    result["attached_files"] = _extract_documents(protocol.get("attachments") or {})

    result["lots"] = []

    protocol_lot_applications = _ensure_list(lots_protocol_info)

    for protocol_lot_application in protocol_lot_applications:
        protocol_lot_application = (
            protocol_lot_application
            if isinstance(protocol_lot_application, dict)
            else {}
        )

        lots = _ensure_list(protocol_lot_application.get("lot"))

        for lot in lots:
            lot = lot if isinstance(lot, dict) else {}

            initial_sum_raw = lot.get("initialSum", 0) or 0
            try:
                initial_sum_val = float(initial_sum_raw)
            except Exception:
                initial_sum_val = 0.0

            lot_result = {
                "guid": lot.get("guid", ""),
                "ordinal_number": lot.get("ordinalNumber", ""),
                "subject": lot.get("subject", ""),
                "initial_sum": initial_sum_val,
                "currency": (lot.get("currency") or {}).get("code", "")
            }

            result["lots"].append(lot_result)

    result["initial_sum"] = sum(float(l.get("initial_sum") or 0) for l in result.get("lots", []))

    return result


def _normalize_purchase(data: dict) -> dict:

    body = (data.get("purchaseNotice", {})).get("body", {})
    item = body.get("item", {}) or {}
    notice = item.get("purchaseNoticeData", {}) or {}
    documentation_delivery = notice.get("documentationDelivery", {}) or {}

    result = {}
    result["registration_number"] = notice.get("registrationNumber")
    result["name"] = notice.get("name")
    result["publication_datetime"] = notice.get("publicationDateTime")

    submission_start = notice.get("applSubmisionStartDate")
    result["submission_start_datetime"] = (
        f"{submission_start}T00:00:00" if submission_start else None
    )
    result["submission_close_datetime"] = notice.get("submissionCloseDateTime")

    if result["submission_start_datetime"] is None:
        delivery_start = documentation_delivery.get("deliveryStartDateTime")
        result["submission_start_datetime"] = f"{delivery_start}T00:00:00" if delivery_start else None

    if result["submission_close_datetime"] is None:
        delivery_end = documentation_delivery.get("deliveryEndDateTime")
        result["submission_close_datetime"] = f"{delivery_end}T23:59:59" if delivery_end else None

    customer = (notice.get("customer") or {}).get("mainInfo") or {}
    result["customer"] = {
        "full_name": customer.get("fullName"),
        "inn": customer.get("inn"),
        "kpp": customer.get("kpp"),
        "ogrn": customer.get("ogrn"),
    }

    contact = notice.get("contact") or {}
    result["contact"] = {
        "last_name": contact.get("lastName"),
        "first_name": contact.get("firstName"),
        "middle_name": contact.get("middleName"),
        "phone": contact.get("phone"),
        "email": contact.get("email"),
    }

    result["apply_request"] = {
        "submission_order": notice.get("applSubmisionOrder"),
        "submission_place": notice.get("applSubmisionPlace")
    }

    result["attached_files"] = _extract_documents(notice.get("attachments") or {})

    result["lots"] = []
    lots = _ensure_list((notice.get("lots") or {}).get("lot"))

    for lot in lots:
        lot = lot or {}
        lot_data = (lot.get("lotData") or {}) if isinstance(lot, dict) else {}

        initial_sum_raw = lot_data.get("initialSum", 0) or lot_data.get("maxContractPrice", 0)
        try:
            initial_sum_val = float(initial_sum_raw)
        except Exception:
            initial_sum_val = 0.0

        lot_result = {
            "guid": lot.get("guid"),
            "ordinal_number": lot.get("ordinalNumber"),
            "subject": lot_data.get("subject"),
            "initial_sum": initial_sum_val,
            "currency": (lot_data.get("currency") or {}).get("code"),
            "application_supply_summ": lot_data.get("applicationSupplySumm"),
            "application_supply_extra": lot_data.get("applicationSupplyExtra"),
            "completing_supply_summ": (lot_data.get("completingSupplyInfo") or {}).get("sum"),
            "items": [],
        }

        lot_items = _ensure_list((lot_data.get("lotItems") or {}).get("lotItem"))
        for it in lot_items:
            it = it or {}
            lot_result["items"].append(
                {
                    "guid": it.get("guid"),
                    "okpd2_code": (it.get("okpd2") or {}).get("code"),
                    "okpd2_name": (it.get("okpd2") or {}).get("name"),
                    "additional_info": it.get("additionalInfo"),
                }
            )

        result["lots"].append(lot_result)

    result["initial_sum"] = sum(float(l.get("initial_sum") or 0) for l in result.get("lots", []))
    return result


def _read_and_parse_xml(archive: zipfile.ZipFile, file_name: str) -> dict:
    """Блокирующая часть (чтение из zip + парсинг XML). Вызывается через
    asyncio.to_thread, чтобы не блокировать event loop."""
    with archive.open(file_name) as file:
        xml_content = file.read()
    data = xmltodict.parse(xml_content)
    return _remove_ns(data)


async def _query_purchase_with_timeout(*, registration_number, filter_type_name) -> Optional[dict]:
    try:
        return (await asyncio.wait_for(
            api_datum_query(
                token=settings.system_token,
                endpoint="get_purchase",
                registration_number=registration_number,
                filter_type_name=filter_type_name,
            ),
            timeout=API_TIMEOUT_SECONDS,
        )).get("data") or {}
    except asyncio.TimeoutError:
        logger.warning(
            "Таймаут get_purchase | reg=%s | filter=%s", registration_number, filter_type_name
        )
        return None


async def _process_protocol_entry(
    archive: zipfile.ZipFile, file_name: str, region: int, filter_number: int
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    try:
        data = await asyncio.to_thread(_read_and_parse_xml, archive, file_name)
        normalized = _normalize_protocol(data)
        normalized["source_file"] = file_name

        customer_name = (normalized.get("customer") or {}).get("full_name")
        work_name = normalized.get("name", "") or ""

        candidates: List[Tuple[int, str]] = []
        if (
            filter_number in (0, 1)
            and REGIONS_ROSSETI.get(region, False)
            and request_filters_rosseti(customer_name, work_name)["result"]
        ):
            candidates.append((1, "Тендеры для Россетей"))

        if filter_number in (0, 2) and request_filters_oem(work_name)["result"]:
            candidates.append((2, "Тендеры для OEM"))

        itm_check = None
        if filter_number in (0, 3):
            itm_check = request_filters_itm(work_name, normalized["lots"])
            if itm_check["result"]:
                candidates.append((3, "Тендеры для ITM"))

        if not candidates:
            return entries

        # Независимые обращения к БД — параллельно.
        purchases = await asyncio.gather(*[
            _query_purchase_with_timeout(
                registration_number=normalized["registration_number"], filter_type_name=name
            )
            for _, name in candidates
        ])

        for (filter_type, filter_type_name), purchase in zip(candidates, purchases):
            if not purchase:
                logger.info(
                    "Протокол прошёл фильтр, но закупка не найдена в БД | reg=%s | filter=%s",
                    normalized.get("registration_number"),
                    filter_type_name,
                )
                continue

            # Отдельная копия на каждый сработавший фильтр — см. пункт 5 в
            # шапке файла про баг с общим объектом.
            entry = copy.deepcopy(normalized)
            entry["guid"] = str(uuid.uuid4())
            entry["region_number"] = region
            entry["filter_type_name"] = filter_type_name

            result_info = purchase.get("result_info") or {}
            documents_list = purchase.get("documents_list") or []

            entry["result_info"], entry["documents_list"] = await process_attached_files_and_merge(
                attached_files=entry["attached_files"],
                tmp_dir=settings.tmp_dir,
                result_info_old=result_info,
                documents_list_old=documents_list,
                protocol_mode=True,
                filter_type=filter_type,
            )
            del entry["attached_files"]

            if filter_type == 3 and itm_check:
                entry["result_info"]["Категория заявки"] = itm_check["filter_name"]

            entries.append(entry)

    except Exception as e:
        logger.exception("Ошибка в файле %s: %s", file_name, e)

    return entries


async def _process_purchase_entry(
    archive: zipfile.ZipFile, file_name: str, region: int, filter_number: int
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    try:
        data = await asyncio.to_thread(_read_and_parse_xml, archive, file_name)
        normalized = _normalize_purchase(data)
        normalized["source_file"] = file_name

        customer_name = (normalized.get("customer") or {}).get("full_name")
        work_name = normalized.get("name", "") or ""

        candidates: List[Tuple[int, str]] = []
        if (
            filter_number in (0, 1)
            and REGIONS_ROSSETI.get(region, False)
            and request_filters_rosseti(customer_name, work_name)["result"]
        ):
            candidates.append((1, "Тендеры для Россетей"))

        if filter_number in (0, 2) and request_filters_oem(work_name)["result"]:
            candidates.append((2, "Тендеры для OEM"))

        itm_check = None
        if filter_number in (0, 3) :
            itm_check = request_filters_itm(work_name, normalized["lots"])
            if itm_check["result"]:
                candidates.append((3, "Тендеры для ITM"))

        if not candidates:
            return entries

        purchases = await asyncio.gather(*[
            _query_purchase_with_timeout(
                registration_number=normalized["registration_number"], filter_type_name=name
            )
            for _, name in candidates
        ])

        for (filter_type, filter_type_name), purchase in zip(candidates, purchases):
            if not purchase:
                # В оригинале этой проверки не было для purchases-версии — при
                # None это падало с AttributeError на purchase.get(...) и
                # маскировалось общим except. См. пункт 6 в шапке файла.
                logger.info(
                    "Закупка прошла фильтр, но не найдена в БД | reg=%s | filter=%s",
                    normalized.get("registration_number"),
                    filter_type_name,
                )
                continue

            entry = copy.deepcopy(normalized)
            entry["guid"] = str(uuid.uuid4())
            entry["region_number"] = region
            entry["filter_type_name"] = filter_type_name

            if filter_type == 1:
                result_info = purchase.get("result_info") or {}
                documents_list = purchase.get("documents_list") or []

                match = re.search(r"для нужд\s+([^.,()\-–—]+)", entry["name"] or "", re.IGNORECASE)
                value = match.group(1).strip() if match else ""
                words = value.split()
                if words:
                    first_word = words[0]
                    result_info["Филиал/РЭС"] = value if len(first_word) > 4 else first_word
                else:
                    result_info["Филиал/РЭС"] = None

                entry["result_info"], entry["documents_list"] = await process_attached_files_and_merge(
                    attached_files=entry["attached_files"],
                    tmp_dir=settings.tmp_dir,
                    result_info_old=result_info,
                    documents_list_old=documents_list,
                    filter_type=1,
                )

            elif filter_type == 2:
                result_info = purchase.get("result_info") or {}
                documents_list = purchase.get("documents_list") or []

                entry["result_info"], entry["documents_list"] = await process_attached_files_and_merge(
                    attached_files=entry["attached_files"],
                    tmp_dir=settings.tmp_dir,
                    result_info_old=result_info,
                    documents_list_old=documents_list,
                    filter_type=2,
                )

                if not entry["result_info"].get("Слова маячки в тз"):
                    entry["result_info"]["Слова маячки в тз"] = "Нету"

            elif filter_type == 3:
                # Как и в оригинале: для ITM в purchases-выгрузке данные
                # берутся из purchase "как есть", без
                # process_attached_files_and_merge (эта ветка была
                # закомментирована в исходном коде — сохраняем как есть).
                entry["result_info"] = purchase.get("result_info") or {}
                entry["documents_list"] = purchase.get("documents_list") or []
                if itm_check:
                    entry["result_info"]["Категория заявки"] = itm_check["filter_name"]

            del entry["attached_files"]
            entries.append(entry)

    except Exception as e:
        logger.exception("Ошибка в файле %s: %s", file_name, e)

    return entries


async def parse_zip_archive_protocols(zip_path: str, region: int, filter_number: int) -> List[Dict[str, Any]]:
    zip_path = os.path.abspath(zip_path)
    all_data: List[Dict[str, Any]] = []
    logger.info("Открываем архив: %s", zip_path)

    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            xml_files = [f for f in archive.namelist() if f.lower().endswith(".xml")]
            logger.info("Найдено XML файлов: %s", len(xml_files))

            semaphore = asyncio.Semaphore(MAX_CONCURRENT_FILES)

            async def _bounded(file_name: str) -> List[Dict[str, Any]]:
                async with semaphore:
                    return await _process_protocol_entry(archive, file_name, region, filter_number)

            results = await asyncio.gather(*[_bounded(f) for f in xml_files])
            for r in results:
                all_data.extend(r)
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

    logger.info("Парсинг завершён. Подходит под фильтры: %s", len(all_data))
    return all_data


async def parse_zip_archive_purchases(zip_path: str, region: int, filter_number: int) -> List[Dict[str, Any]]:
    zip_path = os.path.abspath(zip_path)
    all_data: List[Dict[str, Any]] = []
    logger.info("Открываем архив: %s", zip_path)

    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            xml_files = [f for f in archive.namelist() if f.lower().endswith(".xml")]
            logger.info("Найдено XML файлов: %s", len(xml_files))

            semaphore = asyncio.Semaphore(MAX_CONCURRENT_FILES)

            async def _bounded(file_name: str) -> List[Dict[str, Any]]:
                async with semaphore:
                    return await _process_purchase_entry(archive, file_name, region, filter_number)

            results = await asyncio.gather(*[_bounded(f) for f in xml_files])
            for r in results:
                all_data.extend(r)
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

    logger.info("Парсинг завершён. Подходит под фильтры: %s", len(all_data))
    return all_data