import json
import re
import os
import zipfile
import logging

import xmltodict
import requests
from typing import Dict, List, Any, Union, Optional
from .get_documents_consistent import process_attached_files_and_merge
from .filters.rosseti_filters import request_filters_rosseti
from .filters.oem_filters import request_filters_oem
from .filters.itm_filters import request_filters_itm

TMP_DIR = os.getenv("TMP_DIR", "tmp")
APP_URL = os.getenv("APP_URL")
API_BASE = os.getenv("API_BASE")
TOKEN = os.getenv("SYSTEM_TOKEN")

os.makedirs(TMP_DIR, exist_ok=True)

logger = logging.getLogger(__name__)

# Регионы для фильтров

REGIONS_ROSSETI = {"77": True}


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

def remove_ns(obj):
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            clean_key = k.split(":")[-1]
            new_dict[clean_key] = remove_ns(v)
        return new_dict
    if isinstance(obj, list):
        return [remove_ns(item) for item in obj]
    return obj


def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_protocol(data: dict) -> dict:

    body = data.get("purchaseProtocol", {}).get("body", {})
    item = body.get("item", {}) or {}
    protocol = item.get("purchaseProtocolData", {}) or {}
    purchase_info = protocol.get("purchaseInfo", {}) or {}
    lots_protocol_info = protocol.get("lotApplicationsList", {}).get("protocolLotApplications", {}) or {}

    result = {}

    result["guid"] = purchase_info.get("guid")
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

    # начало работы с документами
    attached_files = protocol.get("attachments") or {}
    document = attached_files.get("document")
    if isinstance(document, str):
        try:
            document = json.loads(document)
        except Exception:
            document = None
    document = ensure_list(document)
    docs = []

    for doc in document:
        docs.append({
            "filename": doc["fileName"],
            "description": doc["description"],
            "url": doc["url"]
        })

    result["attached_files"] = docs
    # окончание работы с документами

    result["lots"] = []

    protocol_lot_applications = ensure_list(lots_protocol_info)

    for protocol_lot_application in protocol_lot_applications:
        protocol_lot_application = (
            protocol_lot_application
            if isinstance(protocol_lot_application, dict)
            else {}
        )

        lots = ensure_list(protocol_lot_application.get("lot"))

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

    # начало работы с документами
    attached_files = protocol.get("attachments") or {}
    document = attached_files.get("document")
    if isinstance(document, str):
        try:
            document = json.loads(document)
        except Exception:
            document = None
    document = ensure_list(document)
    docs = []

    for doc in document:
        docs.append({
            "filename": doc["fileName"],
            "description": doc["description"],
            "url": doc["url"]
        })

    result["attached_files"] = docs

    result["publication_datetime"] = protocol.get("publicationDateTime")
    # окончание работы с документами

    return result


def normalize_purchase(data: dict) -> dict:

    body = data.get("purchaseNotice", {}).get("body", {})
    item = body.get("item", {}) or {}
    notice = item.get("purchaseNoticeData", {}) or {}
    documentation_delivery = notice.get("documentationDelivery", {}) or {}

    result = {}
    result["body"] = body
    result["guid"] = item.get("guid")
    result["registration_number"] = notice.get("registrationNumber")
    result["name"] = notice.get("name")
    result["publication_datetime"] = notice.get("publicationDateTime")

    submission_start = notice.get("applSubmisionStartDate")
    result["submission_start_datetime"] = (
        f"{submission_start}T00:00:00" if submission_start else None
    )
    result["submission_close_datetime"] = notice.get("submissionCloseDateTime")

    if result["submission_start_datetime"] is None:
        result["submission_start_datetime"] = (
            f"{documentation_delivery.get("deliveryStartDateTime")}T00:00:00" if documentation_delivery.get(
                "deliveryStartDateTime") else None
        )

    if result["submission_close_datetime"] is None:
        result["submission_close_datetime"] = (
        f"{documentation_delivery.get("deliveryEndDateTime")}T23:59:59" if documentation_delivery.get(
            "deliveryEndDateTime") else None
    )

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


    # начало работы с документами
    attached_files = notice.get("attachments") or {}
    document = attached_files.get("document")
    if isinstance(document, str):
        try:
            document = json.loads(document)
        except Exception:
            document = None
    document = ensure_list(document)
    docs = []

    for doc in document:
        docs.append({
            "filename": doc["fileName"],
            "description": doc["description"],
            "url": doc["url"]
        })

    result["attached_files"] = docs
    # окончание работы с документами

    result["lots"] = []
    lots = ensure_list((notice.get("lots") or {}).get("lot"))

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

        lot_items = ensure_list((lot_data.get("lotItems") or {}).get("lotItem"))
        for it in lot_items:
            it = it or {}
            lot_result["items"].append(
                {
                    "guid": it.get("guid"),
                    "okpd2_code": (it.get("okpd2") or {}).get("code"),
                    "okpd2_name": (it.get("okpd2") or {}).get("name"),
                    "qty": it.get("qty"),
                    "additional_info": it.get("additionalInfo"),
                }
            )

        result["lots"].append(lot_result)

    result["initial_sum"] = sum(float(l.get("initial_sum") or 0) for l in result.get("lots", []))
    return result


def parse_zip_archive_protocols(zip_path: str, region: int, filter_number: int) -> List[Dict[str, Any]]:
    zip_path = os.path.abspath(zip_path)
    all_data: List[Dict[str, Any]] = []
    logger.info("Открываем архив: %s", zip_path)

    with (zipfile.ZipFile(zip_path, "r") as archive):
        xml_files = [f for f in archive.namelist() if f.lower().endswith(".xml")]
        logger.info("Найдено XML файлов: %s", len(xml_files))

        for file_name in xml_files:
            try:
                with archive.open(file_name) as file:
                    xml_content = file.read()

                data = xmltodict.parse(xml_content)
                data = remove_ns(data)
                normalized = normalize_protocol(data)
                normalized["source_file"] = file_name

                customer_name = (normalized.get("customer") or {}).get("full_name")
                work_name = normalized.get("name", "") or ""

                if (filter_number == 0 or filter_number == 1) and REGIONS_ROSSETI.get(region, False) and request_filters_rosseti(customer_name, work_name):
                    normalized["region_number"] = region
                    normalized["filter_type_name"] = "Тендеры для Россетей"

                    # Обращение, получение данных и передача
                    purchase_response = requests.post(
                        f"{APP_URL}{API_BASE}/get_purchase",
                        json={"token": TOKEN, "registration_number": normalized["registration_number"]},
                        timeout=30,
                    )

                    purchase_response.raise_for_status()

                    purchase = purchase_response.json().get("data") or {}

                    if not purchase:

                        logger.info(
                            "Протокол прошёл фильтр, но закупка не найдена в БД | reg=%s",
                            normalized.get("registration_number"),
                        )

                        continue

                    result_info = purchase.get("result_info") or {}

                    documents_list = purchase.get("documents_list") or []

                    normalized["result_info"], normalized["documents_list"] = process_attached_files_and_merge(
                        attached_files=normalized["attached_files"],
                        tmp_dir=TMP_DIR,
                        result_info_old=result_info,
                        documents_list_old=documents_list,
                        protocol_mode=True,
                        filter_type = 1
                    )

                    del normalized["attached_files"]

                    print("result_info - protocols")
                    print(normalized["result_info"])

                    print("documents_list - protocols")
                    print(normalized["documents_list"])
                    all_data.append(normalized)

                if (filter_number == 0 or filter_number == 2) and request_filters_oem(work_name):
                    normalized["region_number"] = region
                    normalized["filter_type_name"] = "Тендеры для OEM"

                    # Обращение, получение данных и передача
                    purchase_response = requests.post(
                        f"{APP_URL}{API_BASE}/get_purchase",
                        json={"token": TOKEN, "registration_number": normalized["registration_number"]},
                        timeout=30,
                    )

                    purchase_response.raise_for_status()

                    purchase = purchase_response.json().get("data") or {}

                    if not purchase:
                        logger.info(
                            "Протокол прошёл фильтр, но закупка не найдена в БД | reg=%s",
                            normalized.get("registration_number"),
                        )

                        continue

                    normalized["result_info"] = purchase.get("result_info") or {}

                    normalized["documents_list"] = purchase.get("documents_list") or []

                    # normalized["result_info"], normalized["documents_list"] = process_attached_files_and_merge(
                    #     attached_files=normalized["attached_files"],
                    #     tmp_dir=TMP_DIR,
                    #     result_info_old=result_info,
                    #     documents_list_old=documents_list,
                    #     protocol_mode=True,
                    #     filter_type = 2
                    # )
                    #
                    # del normalized["attached_files"]
                    #
                    # print("result_info - protocols")
                    # print(normalized["result_info"])
                    #
                    # print("documents_list - protocols")
                    # print(normalized["documents_list"])
                    all_data.append(normalized)

                if (filter_number == 0 or filter_number == 3) and request_filters_itm(work_name):
                    normalized["region_number"] = region
                    normalized["filter_type_name"] = "Тендеры для ITM"

                    # Обращение, получение данных и передача
                    purchase_response = requests.post(
                        f"{APP_URL}{API_BASE}/get_purchase",
                        json={"token": TOKEN, "registration_number": normalized["registration_number"]},
                        timeout=30,
                    )

                    purchase_response.raise_for_status()

                    purchase = purchase_response.json().get("data") or {}

                    if not purchase:
                        logger.info(
                            "Протокол прошёл фильтр, но закупка не найдена в БД | reg=%s",
                            normalized.get("registration_number"),
                        )

                        continue

                    result_info = purchase.get("result_info") or {}

                    documents_list = purchase.get("documents_list") or []

                    normalized["result_info"], normalized["documents_list"] = process_attached_files_and_merge(
                        attached_files=normalized["attached_files"],
                        tmp_dir=TMP_DIR,
                        result_info_old=result_info,
                        documents_list_old=documents_list,
                        protocol_mode=True,
                        filter_type = 3
                    )

                    del normalized["attached_files"]

                    all_data.append(normalized)


            except Exception as e:
                logger.exception("Ошибка в файле %s: %s", file_name, e)

    logger.info("Парсинг завершён. Подходит под фильтры: %s", len(all_data))
    os.remove(zip_path)
    return all_data

def parse_zip_archive_purchases(zip_path: str, region: int, filter_number: int) -> List[Dict[str, Any]]:
    zip_path = os.path.abspath(zip_path)
    all_data: List[Dict[str, Any]] = []
    logger.info("Открываем архив: %s", zip_path)

    with (zipfile.ZipFile(zip_path, "r") as archive):
        xml_files = [f for f in archive.namelist() if f.lower().endswith(".xml")]
        logger.info("Найдено XML файлов: %s", len(xml_files))

        for file_name in xml_files:
            try:
                with archive.open(file_name) as file:
                    xml_content = file.read()

                data = xmltodict.parse(xml_content)
                data = remove_ns(data)
                normalized = normalize_purchase(data)
                normalized["source_file"] = file_name

                customer_name = (normalized.get("customer") or {}).get("full_name")
                work_name = normalized.get("name", "") or ""

                if (filter_number == 0 or filter_number == 1) and REGIONS_ROSSETI.get(region, False) and request_filters_rosseti(customer_name, work_name):
                    normalized["region_number"] = region
                    normalized["filter_type_name"] = "Тендеры для Россетей"

                    # Обращение, получение данных и передача
                    purchase_response = requests.post(
                        f"{APP_URL}{API_BASE}/get_purchase",
                        json={"token": TOKEN, "registration_number": normalized["registration_number"]},
                        timeout=30,
                    )

                    purchase_response.raise_for_status()

                    purchase = purchase_response.json().get("data", {})

                    result_info = purchase.get("result_info") or {}
                    documents_list = purchase.get("documents_list") or []

                    match = re.search(r'для нужд\s+([^.,()\-–—]+)', normalized["name"], re.IGNORECASE)

                    if match:

                        value = match.group(1).strip()

                        first_word = value.split()[0]

                        result_info["Филиал/РЭС"] = value if len(first_word) > 4 else first_word

                    else:

                        result_info["Филиал/РЭС"] = None


                    normalized["result_info"], normalized["documents_list"] = process_attached_files_and_merge(
                        attached_files=normalized["attached_files"],
                        tmp_dir=TMP_DIR,
                        result_info_old = result_info,
                        documents_list_old = documents_list,
                        filter_type = 1
                    )

                    del normalized["attached_files"]

                    all_data.append(normalized)

                if (filter_number == 0 or filter_number == 2)  and request_filters_oem(work_name):

                    normalized["region_number"] = region
                    normalized["filter_type_name"] = "Тендеры для OEM"

                    # Обращение, получение данных и передача
                    purchase_response = requests.post(
                        f"{APP_URL}{API_BASE}/get_purchase",
                        json={"token": TOKEN, "registration_number": normalized["registration_number"]},
                        timeout=30,
                    )

                    purchase_response.raise_for_status()

                    purchase = purchase_response.json().get("data", {})

                    normalized["result_info"] = purchase.get("result_info") or {}

                    normalized["documents_list"] = purchase.get("documents_list") or []

                    # result_info = purchase.get("result_info") or {}
                    #
                    # documents_list = purchase.get("documents_list") or []
                    #
                    # normalized["result_info"], normalized["documents_list"] = process_attached_files_and_merge(
                    #     attached_files=normalized["attached_files"],
                    #     tmp_dir=TMP_DIR,
                    #     result_info_old=result_info,
                    #     documents_list_old=documents_list,
                    #     filter_type = 2
                    # )

                    del normalized["attached_files"]

                    all_data.append(normalized)

                if (filter_number == 0 or filter_number == 3) and request_filters_itm(work_name):

                    normalized["region_number"] = region
                    normalized["filter_type_name"] = "Тендеры для ITM"

                    # Обращение, получение данных и передача
                    purchase_response = requests.post(
                        f"{APP_URL}{API_BASE}/get_purchase",
                        json={"token": TOKEN, "registration_number": normalized["registration_number"]},
                        timeout=30,
                    )

                    purchase_response.raise_for_status()

                    purchase = purchase_response.json().get("data", {})

                    normalized["result_info"] = purchase.get("result_info") or {}

                    normalized["documents_list"] = purchase.get("documents_list") or []

                    # result_info = purchase.get("result_info") or {}
                    #
                    # documents_list = purchase.get("documents_list") or []
                    #
                    # normalized["result_info"], normalized["documents_list"] = process_attached_files_and_merge(
                    #     attached_files=normalized["attached_files"],
                    #     tmp_dir=TMP_DIR,
                    #     result_info_old=result_info,
                    #     documents_list_old=documents_list,
                    #     filter_type = 2
                    # )

                    del normalized["attached_files"]

                    all_data.append(normalized)

            except Exception as e:
                logger.exception("Ошибка в файле %s: %s", file_name, e)
    logger.info("Парсинг завершён. Подходит под фильтры: %s", len(all_data))
    os.remove(zip_path)
    return all_data