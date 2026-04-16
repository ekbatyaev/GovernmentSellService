import json
import re
import os
import zipfile
import logging
import xmltodict
from typing import Dict, List, Any
from .document_consistent import process_attached_files_and_merge

TMP_DIR = os.getenv("TMP_DIR", "tmp")
os.makedirs(TMP_DIR, exist_ok=True)

logger = logging.getLogger(__name__)

# Фильтры для отбора документов

FILTERS_CUSTOMER = ["РОССЕТИ МОСКОВСКИЙ РЕГИОН"]

FILTERS_JOB_NAME = [
    r"РТП-10/0,4кВ",
    r"ТП-10/0,4кВ",
    r"РП 10 кВ",
    r"строительств[а-я]*\s+РТП",
    r"реконструкци[а-я]*\s+ТП",
    r"ПИР",
    r"СМР",
    r"ПНР",
    r"право\s+заключени[а-я]*\s+рамочн[а-я]*\s+соглашени[а-я]*",
    r"определени[а-я]*\s+поставщик[а-я]*\s+на\s+поставк[а-я]*",
    r"замен[а-я]*\s+оборудовани[а-я]*",
    r"проектировани[а-я]*\s+сет[а-я]*",
    r"для нужд МКС",
    r"РТП-20/0,4кВ",
    r"ТП-20/0,4кВ",
    r"РП 20 кВ",
]

FILTERS_JOB_EXCLUDE = [
    r"\bПС-\s*\d+(?:/\d+)*\s*кВ\b",
]

JOB_PATTERNS = [re.compile(p, re.IGNORECASE) for p in FILTERS_JOB_NAME]
JOB_EXCLUDE_PATTERNS = [re.compile(p, re.IGNORECASE) for p in FILTERS_JOB_EXCLUDE]


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


def normalize_value(value):
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    return value


def split_merged_value(value: str):
    """
    Если extract_tender_fields уже вернул строку с несколькими значениями
    через ;, перенос строки или запятую, разбиваем аккуратно.
    """
    parts = []
    for chunk in str(value).replace("\n", ";").split(";"):
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    return parts


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
    result["submission_start_datetime"] = f"{submission_start}T00:00:00"
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


def parse_zip_archive(zip_path: str) -> List[Dict[str, Any]]:
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

                ok_customer = any(f in str(customer_name or "") for f in FILTERS_CUSTOMER)
                ok_job = any(p.search(work_name) for p in JOB_PATTERNS)
                excluded_names = any(p.search(work_name) for p in JOB_EXCLUDE_PATTERNS)

                has_from = bool(re.search(r"\bот\s+(РП|ТП|РТП)\b", work_name, re.IGNORECASE))
                work_name_without_from = re.sub(r"\bот\s+(РП|ТП|РТП)\b", "", work_name, flags=re.IGNORECASE)
                has_without_from = bool(re.search(r"\b(РП|ТП|РТП)\b", work_name_without_from, re.IGNORECASE))

                excluded_job = excluded_names or (has_from and not has_without_from)

                if ok_customer and ok_job and not excluded_job:

                    normalized["result_info"] = process_attached_files_and_merge(
                        attached_files=normalized["attached_files"],
                        tmp_dir=TMP_DIR
                    )

                    del normalized["attached_files"]

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