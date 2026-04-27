import json
import re
import os
import zipfile
import logging

import xmltodict
import requests
from typing import Dict, List, Any
from .document_consistent import process_attached_files_and_merge

TMP_DIR = os.getenv("TMP_DIR", "tmp")
APP_URL = os.getenv("APP_URL")
API_BASE = os.getenv("API_BASE")
TOKEN = os.getenv("SYSTEM_TOKEN")

os.makedirs(TMP_DIR, exist_ok=True)

logger = logging.getLogger(__name__)

# Фильтры для отбора документов

FILTERS_CUSTOMER = ["РОССЕТИ МОСКОВСКИЙ РЕГИОН"]

FILTERS_JOB_NAME = [
    r"РТП-10/0,4\s*кВ",
    r"ТП-10/0,4\s*кВ",
    r"РП\s*-?\s*10\s*кВ",
    r"РП\s*-?\s*20\s*кВ",
    r"БКТП\s*-?\s*(?:10|20)?/?0?,?4?\s*кВ?",
    r"КТП\s*-?\s*\d*[-/]?(?:10|6)?/?0?,?4?\s*кВ?",
    r"строительств[а-я]*\s+РТП",
    r"строительств[а-я]*\s+РП",
    r"строительств[а-я]*\s+ТП",
    r"строительств[а-я]*\s+БКТП",
    r"строительств[а-я]*\s+КТП",
    r"реконструкци[а-я]*\s+ТП",
    r"реконструкци[а-я]*\s+РП",
    r"реконструкци[а-я]*\s+РТП",
    r"реконструкци[а-я]*\s+БКТП",
    r"реконструкци[а-я]*\s+КТП",
    r"модернизаци[а-я]*\s+РП",
    r"проектно\s*[-–—]?\s*изыскательск[а-я]*\s+работ[а-я]*",
    r"ПИР",
    r"СМР",
    r"ПНР",
    r"право\s+заключени[а-я]*\s+рамочн[а-я]*\s+соглашени[а-я]*",
    r"определени[а-я]*\s+поставщик[а-я]*\s+на\s+поставк[а-я]*",
    r"замен[а-я]*\s+оборудовани[а-я]*",
    r"проектировани[а-я]*\s+сет[а-я]*",
    r"для нужд МКС",
    r"РТП-20/0,4\s*кВ",
    r"ТП-20/0,4\s*кВ",
]

FILTERS_JOB_EXCLUDE_HARD = [
    r"\bавто(?:мобил[а-я]*|транспорт[а-я]*|техник[а-я]*|шин[а-я]*|запчаст[а-я]*)\b",
    r"бензоинструмента",
    r"переустройств[а-я]*",
    r"кабельн[а-я]*\s+исполнени[а-я]*",
    r"воздушн[а-я]*\s+участк[а-я]*",
]

FILTERS_JOB_EXCLUDE_SOFT = [
    r"\bПС(?:-\s*|\s+)(?:110|220|500)(?:/\d+)*\s*кВ\b",
]

TARGET_OBJECT_PATTERNS = [
    r"\bТП\s*-?\s*(?:6|10|20)?(?:\s*/\s*0\s*,?\s*4)?\s*(?:кВ)?\b",
    r"\bРТП\s*-?\s*(?:6|10|20)?(?:\s*/\s*0\s*,?\s*4)?\s*(?:кВ)?\b",
    r"\bРП\s*-?\s*(?:6|10|20)\s*(?:кВ)?\b",
    r"\bБКТП\s*-?\s*(?:6|10|20)?(?:\s*/\s*0\s*,?\s*4)?\s*(?:кВ)?\b",
    r"\bКТП\s*-?\s*\d*(?:[-/]\s*(?:6|10|20))?(?:\s*/\s*0\s*,?\s*4)?\s*(?:кВ)?\b",
]

JOB_PATTERNS = [re.compile(p, re.IGNORECASE) for p in FILTERS_JOB_NAME]
JOB_EXCLUDE_HARD_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in FILTERS_JOB_EXCLUDE_HARD
]

JOB_EXCLUDE_SOFT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in FILTERS_JOB_EXCLUDE_SOFT
]
TARGET_PATTERNS = [re.compile(p, re.IGNORECASE) for p in TARGET_OBJECT_PATTERNS]


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

    result = {}

    result["guid"] = purchase_info.get("guid")
    result["registration_number"] = purchase_info.get("purchaseNoticeNumber")
    result["name"] = purchase_info.get("name")

    customer = (protocol.get("customer") or {}).get("mainInfo") or {}
    result["customer"] = {
        "full_name": customer.get("fullName"),
        "inn": customer.get("inn"),
        "kpp": customer.get("kpp"),
        "ogrn": customer.get("ogrn"),
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

    result["publication_datetime"] = protocol.get("publicationDateTime")
    # окончание работы с документами

    return result

def request_filters(customer_name, work_name)-> bool:

    ok_customer = any(f in customer_name for f in FILTERS_CUSTOMER)
    excluded_hard = any(p.search(work_name) for p in JOB_EXCLUDE_HARD_PATTERNS)
    excluded_soft = any(p.search(work_name) for p in JOB_EXCLUDE_SOFT_PATTERNS)

    ok_job_raw = any(p.search(work_name) for p in JOB_PATTERNS)
    has_target_object = any(p.search(work_name) for p in TARGET_PATTERNS)

    has_group_objects = bool(
        re.search(
            r"(?:по\s+[А-ЯЁа-яё\-]+(?:ому|ему)\s+району|по\s+приказу|по\s+распоряжени[а-я]*|по\s+программ[а-я]*)"
            r".{0,250}"
            r"\(\s*\d+\s+объект",
            work_name,
            re.IGNORECASE
        )
    )

    has_metering = bool(
        re.search(
            r"установк[а-я]*\s+прибор[а-я]*",
            work_name,
            re.IGNORECASE
        )
    )

    has_electro_supply = bool(
        re.search(
            r"поставк[а-я]*.*(?:коммутационн[а-я]*|электромонтажн[а-я]*|"
            r"электроустановочн[а-я]*|электроизоляционн[а-я]*|"
            r"светотехническ[а-я]*|электротехническ[а-я]*|электронн[а-я]*|"
            r"фонар[а-я]*|запасн[а-я]*\s+част[а-я]*)",
            work_name,
            re.IGNORECASE
        )
    )

    has_tech_connection = bool(
        re.search(
            r"(техническ[а-я]*\s+услови[а-я]*|технологическ[а-я]*\s+присоединени[а-я]*)",
            work_name,
            re.IGNORECASE
        )
    )

    has_rosseti_context = bool(
        re.search(
            r"(Россети\s+Московск[а-я]*\s+регион|для\s+нужд\s+(?:МКС|Новая\s+Москва))",
            work_name,
            re.IGNORECASE
        )
    )

    has_zes_order_objects = bool(
        re.search(
            r"по\s+объектам\s+ЗЭС\s+распоряжени[а-я]*",
            work_name,
            re.IGNORECASE
        )
    )

    has_bktp_in_tu = bool(
        re.search(
            r"(техническ[а-я]*\s+услови[а-я]*|п\.\s*11).{0,120}\b\d*\s*БКТП\b",
            work_name,
            re.IGNORECASE
        )
    )

    ok_job = ok_job_raw and (
            has_target_object
            or has_group_objects
            or has_metering
            or has_electro_supply
            or has_zes_order_objects
            or has_bktp_in_tu
            or (has_tech_connection and has_rosseti_context)
    )

    has_from = bool(
        re.search(r"\bот\s+(РП|ТП|РТП|БКТП|КТП)\b", work_name, re.IGNORECASE)
    )

    is_land_release_line_work = bool(
        re.search(
            r"для\s+освобождени[а-я]*\s+земельн[а-я]*\s+участк[а-я]*",
            work_name,
            re.IGNORECASE
        )
        and re.search(
            r"\b(?:КВЛ|КЛ|ВЛЗ|ВЛ)\s*-?\s*\d+(?:\s*,\s*\d+)?\s*кВ\b",
            work_name,
            re.IGNORECASE
        )
        and not re.search(
            r"\b(?:строительств[а-я]*|реконструкци[а-я]*|модернизаци[а-я]*)\s+"
            r"(?:ТП|РТП|РП|БКТП|КТП)\b",
            work_name,
            re.IGNORECASE
        )
    )

    work_name_without_from = re.sub(
        r"\bот\s+(РП|ТП|РТП|БКТП|КТП)\b",
        "",
        work_name,
        flags=re.IGNORECASE
    )

    has_without_from = bool(
        re.search(r"\b(РП|ТП|РТП|БКТП|КТП)\b", work_name_without_from, re.IGNORECASE)
    )

    only_source_object = has_from and not has_without_from

    source_object_allowed = bool(
        re.search(
            r"(для\s+нужд\s+МКС|ПИР|СМР|ПНР|строительств[а-я]*|технологическ[а-я]*\s+присоединени[а-я]*)",
            work_name,
            re.IGNORECASE
        )
    )

    excluded_job = (
            excluded_hard
            or is_land_release_line_work
            or (excluded_soft and not has_target_object)
            or (only_source_object and not source_object_allowed)
    )

    if ok_customer and ok_job and not excluded_job:
        return True
    return False

def parse_zip_archive_protocols(zip_path: str) -> List[Dict[str, Any]]:
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

                if request_filters(customer_name, work_name):
                    print(normalized["registration_number"])

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
                        protocol_mode=True
                    )

                    del normalized["attached_files"]

                    print("result_info - protocols")
                    print(normalized["result_info"])

                    print("documents_list - protocols")
                    print(normalized["documents_list"])

                    all_data.append(normalized)


            except Exception as e:
                logger.exception("Ошибка в файле %s: %s", file_name, e)

    logger.info("Парсинг завершён. Подходит под фильтры: %s", len(all_data))
    os.remove(zip_path)
    return all_data


def normalize_purchase(data: dict) -> dict:

    body = data.get("purchaseNotice", {}).get("body", {})
    item = body.get("item", {}) or {}
    notice = item.get("purchaseNoticeData", {}) or {}

    result = {}

    result["guid"] = item.get("guid")
    result["registration_number"] = notice.get("registrationNumber")
    result["name"] = notice.get("name")
    result["publication_datetime"] = notice.get("publicationDateTime")
    submission_start = notice.get("applSubmisionStartDate")
    result["submission_start_datetime"] = (
        f"{submission_start}T00:00:00" if submission_start else None
    )
    result["submission_close_datetime"] = notice.get("submissionCloseDateTime")

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

        initial_sum_raw = lot_data.get("initialSum", 0) or 0
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


def parse_zip_archive_purchases(zip_path: str) -> List[Dict[str, Any]]:
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

                if request_filters(customer_name, work_name):

                    # Обращение, получение данных и передача
                    purchase_response = requests.post(
                        f"{APP_URL}{API_BASE}/get_purchase",
                        json={"token": TOKEN, "registration_number": normalized["registration_number"]},
                        timeout=30,
                    )

                    purchase_response.raise_for_status()

                    purchase = purchase_response.json().get("data", {})

                    result_info = purchase.get("result_info") or {}

                    match = re.search(r'для нужд\s+([^.,()\-–—]+)', normalized["name"], re.IGNORECASE)

                    if match:

                        value = match.group(1).strip()

                        first_word = value.split()[0]

                        result_info["Филиал/РЭС"] = value if len(first_word) > 4 else first_word

                    else:

                        result_info["Филиал/РЭС"] = None

                    documents_list = purchase.get("documents_list") or []

                    normalized["result_info"], normalized["documents_list"] = process_attached_files_and_merge(
                        attached_files=normalized["attached_files"],
                        tmp_dir=TMP_DIR,
                        result_info_old = result_info,
                        documents_list_old = documents_list
                    )

                    del normalized["attached_files"]

                    print("result_info")
                    print(normalized["result_info"])
                    print("documents_list")
                    print(normalized["documents_list"])
                    all_data.append(normalized)

            except Exception as e:
                logger.exception("Ошибка в файле %s: %s", file_name, e)
    logger.info("Парсинг завершён. Подходит под фильтры: %s", len(all_data))
    os.remove(zip_path)
    return all_data

if __name__ == "__main__":
    merged_fields = process_attached_files_and_merge(
        attached_files=[
            {
                "filename": "624 Протокол итоговый.docx",
                "description": "",
                "url": "URL_СЮДА"
            }
        ],
        tmp_dir=TMP_DIR,
    )