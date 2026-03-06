import json
import re

import xmltodict
from typing import Dict, List, Any
import os
import zipfile
import requests
from pathlib import Path

# Фильтр по заказчику

FILTERS_CUSTOMER = ["РОССЕТИ МОСКОВСКИЙ РЕГИОН"]

FILTERS_JOB_NAME = [
    r'РТП-10/0,4кВ',
    r'ТП-10/0,4кВ',
    r'РП 10 кВ',
    r'строительств[а-я]*\s+РТП',
    r'реконструкци[а-я]*\s+ТП',
    r'ПИР',
    r'СМР',
    r'ПНР',
    r'право\s+заключени[а-я]*\s+рамочн[а-я]*\s+соглашени[а-я]*',
    r'определени[а-я]*\s+поставщик[а-я]*\s+на\s+поставк[а-я]*',
    r'замен[а-я]*\s+оборудовани[а-я]*',
    r'проектировани[а-я]*\s+сет[а-я]*',
    r'для нужд МКС',
    r'РТП-20/0,4кВ',
    r'ТП-20/0,4кВ',
    r'РП 20 кВ'
]

# ----------------------------
# Удаление namespace
# ----------------------------
def remove_ns(obj):
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            clean_key = k.split(":")[-1]
            new_dict[clean_key] = remove_ns(v)
        return new_dict
    elif isinstance(obj, list):
        return [remove_ns(item) for item in obj]
    else:
        return obj


# ----------------------------
# Если объект не список — делаем список
# ----------------------------
def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]

# ----------------------------
# Скачиваем прикрепленные файлы
# ----------------------------

# def download_file_or_zip(result: dict, out_file: str | None = None) -> str:
#     archive_name = result.get("file_name")
#     archive_url = result.get("download_link")
#     print(archive_name, archive_url)
#     if not out_file:
#         out_file = f"tmp/{archive_name}"
#
#     # Минимально необходимые заголовки
#     headers = {
#         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
#         'Referer': 'https://zakupki.gov.ru/',
#         'Accept': '*/*',
#     }
#
#     with requests.get(archive_url, headers=headers, stream=True, timeout=15) as r:
#         r.raise_for_status()
#         with open(out_file, "wb") as f:
#             for chunk in r.iter_content(chunk_size=1024 * 1024):
#                 if chunk:
#                     f.write(chunk)
#
#     return out_file


def _fix_zip_filename(name: str) -> str:
    """
    Исправляет кодировку имени файла в ZIP (cp866/cp1251 -> utf-8)
    """
    try:
        # Чаще всего в госархивах это cp866
        return name.encode('cp437').decode('cp866')
    except Exception:
        try:
            # Иногда бывает cp1251
            return name.encode('cp437').decode('cp1251')
        except Exception:
            return name


def download_and_extract(result: dict, out_file: str | None = None) -> str:
    """
    Скачивает файл и распаковывает его, если это ZIP архив.
    Исправляет кодировку имен файлов.
    """

    archive_name = result.get("file_name")
    archive_url = result.get("download_link")

    if not archive_name or not archive_url:
        raise ValueError("Missing fileName or url in result")

    if not out_file:
        out_file = f"tmp/{archive_name}"

    Path("tmp").mkdir(exist_ok=True)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://zakupki.gov.ru/',
        'Accept': '*/*',
    }

    print(f"📥 Скачиваю: {archive_name}")

    with requests.get(archive_url, headers=headers, stream=True, timeout=30) as r:
        r.raise_for_status()
        with open(out_file, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    print(f"✅ Скачано: {out_file}")
    print(f"📊 Размер: {os.path.getsize(out_file)} байт")

    if not zipfile.is_zipfile(out_file):
        print("📄 Файл не является ZIP")
        return out_file

    extract_to = os.path.splitext(out_file)[0]
    Path(extract_to).mkdir(exist_ok=True)

    print(f"📦 Распаковываю ZIP в: {extract_to}")

    try:
        with zipfile.ZipFile(out_file, 'r') as zip_ref:
            files = zip_ref.infolist()

            for member in files:
                fixed_name = _fix_zip_filename(member.filename)
                member.filename = fixed_name  # заменяем имя

                zip_ref.extract(member, extract_to)

            print(f"✅ Распаковано файлов: {len(files)}")

            if files:
                print("📄 Файлы:")
                for i, f in enumerate(files[:5]):
                    print(f"   {i + 1}. {_fix_zip_filename(f.filename)}")

        return extract_to

    except Exception as e:
        print(f"❌ Ошибка при распаковке: {e}")
        return out_file

# ----------------------------
# Нормализация одной закупки
# ----------------------------
def normalize_purchase(data: dict) -> dict:
    body = data.get("purchaseNotice", {}).get("body", {})
    item = body.get("item", {})
    notice = item.get("purchaseNoticeData", {})

    result = {}

    # --- Основная информация ---
    result["guid"] = item.get("guid")
    result["registration_number"] = notice.get("registrationNumber")
    result["name"] = notice.get("name")
    result["publication_datetime"] = notice.get("publicationDateTime")
    result["submission_close_datetime"] = notice.get("submissionCloseDateTime")

    # --- Заказчик ---
    customer = notice.get("customer", {}).get("mainInfo", {})
    result["customer"] = {
        "full_name": customer.get("fullName"),
        "inn": customer.get("inn"),
        "kpp": customer.get("kpp"),
        "ogrn": customer.get("ogrn"),
    }

    # --- Контакт ---
    contact = notice.get("contact", {})
    result["contact"] = {
        "last_name": contact.get("lastName"),
        "first_name": contact.get("firstName"),
        "middle_name": contact.get("middleName"),
        "phone": contact.get("phone"),
        "email": contact.get("email"),
    }

    # -- Подача заявки --
    result["apply_request"] = {
        "submission_order": notice.get("applSubmisionOrder"),
        "submission_place": notice.get("applSubmisionPlace"),
        "submission_start_date": notice.get("applSubmisionStartDate"),
    }


    attached_files = notice.get("attachments", {})
    document = attached_files.get("document")

    # Если это строка — распарсить
    if isinstance(document, str):
        document = json.loads(document)

    # Если это словарь — завернуть в список
    if isinstance(document, dict):
        document = [document]

    doc_info = []
    for doc in document:
        if isinstance(doc, str):
            doc = json.loads(doc)
        doc_info.append({
                "file_name": doc.get("fileName"),
                "description": doc.get("description"),
                "download_link": doc.get("url")
            })
    result["attached_files"] = doc_info

    # --- Лоты ---
    result["lots"] = []

    lots = ensure_list(notice.get("lots", {}).get("lot"))

    for lot in lots:
        lot_data = lot.get("lotData", {})

        lot_result = {
            "guid": lot.get("guid"),
            "ordinal_number": lot.get("ordinalNumber"),
            "subject": lot_data.get("subject"),
            "initial_summ": float(lot_data.get("initialSum", 0) or 0),
            "currency": lot_data.get("currency", {}).get("code"),
            "application_supply_summ": lot_data.get("applicationSupplySumm"),
            "application_supply_extra": lot_data.get("applicationSupplyExtra"),
            "completing_supply_summ": lot_data.get("completingSupplyInfo", {}).get("sum"),
            "items": []
        }

        lot_items = ensure_list(
            lot_data.get("lotItems", {}).get("lotItem")
        )

        for item in lot_items:
            lot_result["items"].append({
                "guid": item.get("guid"),
                "okpd2_code": item.get("okpd2", {}).get("code"),
                "okpd2_name": item.get("okpd2", {}).get("name"),
                "qty": item.get("qty"),
                "additional_info": item.get("additionalInfo"),
            })

        result["lots"].append(lot_result)
    result["initial_summ"] = result.get("lots")[0].get("initialSum")
    return result


# ----------------------------
# Парсинг ZIP архива
# ----------------------------
def parse_zip_archive(zip_path: str) -> List[Dict[str, Any]]:
    all_data = []

    print(f"Открываем архив: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as archive:
        xml_files = [f for f in archive.namelist() if f.lower().endswith(".xml")]
        print(f"Найдено XML файлов: {len(xml_files)}")

        for file_name in xml_files:
            print(f"Обработка: {file_name}")

            with archive.open(file_name) as file:
                try:
                    xml_content = file.read()

                    # XML → dict
                    data = xmltodict.parse(xml_content)

                    # Убираем namespace
                    data = remove_ns(data)
                    # pprint(data)

                    # Нормализация
                    normalized = normalize_purchase(data)
                    normalized["sourceFile"] = file_name
                    customer_name = normalized.get("customer", {}).get("full_name")
                    work_name = normalized.get("name", "")
                    if any(f in str(customer_name) for f in FILTERS_CUSTOMER) and any(re.search(pattern, work_name, re.IGNORECASE) for pattern in FILTERS_JOB_NAME):
                        all_data.append(normalized)
                        attached_files = normalized.get("attached_files")
                        # for doc in attached_files:
                        #     download_and_extract(doc)
                        print("  ✓ Добавлено (соответствует фильтру)")
                    else:
                        print("  ✗ Пропущено (не соответствует фильтру)")

                except Exception as e:
                    print(f"Ошибка в файле {file_name}: {e}")

    print("Парсинг завершён.")
    return all_data


# ----------------------------
# Краткий вывод
# ----------------------------
# def print_summary(data: List[Dict[str, Any]]) -> None:
#     print("\n" + "=" * 80)
#     print(f"НАЙДЕНО ЗАКУПОК: {len(data)}")
#     print("=" * 80)
#
#     for i, purchase in enumerate(data, 1):
#         print(f"\n{i}. {purchase.get('name')}")
#         print(f"   Рег. номер: {purchase.get('registrationNumber')}")
#         print(f"   Заказчик: {purchase.get('customer', {}).get('fullName')}")
#
#         total_sum = sum(lot.get("initialSum", 0) for lot in purchase.get("lots", []))
#         print(f"   Общая сумма лотов: {total_sum:,.2f} RUB")
#
#         for lot in purchase.get("lots", []):
#             print(f"      Лот {lot.get('ordinalNumber')} → {lot.get('subject')}")
#             print(f"         Сумма: {lot.get('initialSum'):,.2f}")
#             print(f"         Позиций: {len(lot.get('items', []))}")


# ----------------------------
# MAIN
# ----------------------------
if __name__ == "__main__":
    zip_file_path = "tmp\\019B240C77FE78FF976E981DAED8E4FE.zip"

    results = parse_zip_archive(zip_file_path)
    with open("results.json", 'w', encoding = 'utf-8') as file:
        json.dump(results, file, ensure_ascii = False, indent = 4)

    # pprint(results)