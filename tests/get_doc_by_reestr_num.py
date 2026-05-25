import os
import uuid
import json
import time
import zipfile
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

import requests
import xmltodict
from dotenv import load_dotenv
from lxml import etree
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


load_dotenv()

BASE_URL = os.getenv("BASE_URL")  # например: https://int.zakupki.gov.ru/eis-integration/services/getDocsIP
TOKEN = os.getenv("TOKEN")        # individualPerson_token
TMP_DIR = os.getenv("TMP_DIR", "tmp")

SOAP_TIMEOUT = int(os.getenv("SOAP_TIMEOUT", "60"))
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "120"))

Path(TMP_DIR).mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


def build_session() -> requests.Session:
    session = requests.Session()

    retry = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )

    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=20,
        pool_maxsize=20,
    )

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
    })

    return session


session = build_session()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def generate_uid() -> str:
    return str(uuid.uuid4())


def iso_datetime_now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


def remove_ns(obj):
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            clean_key = k.split(":")[-1]
            result[clean_key] = remove_ns(v)
        return result

    if isinstance(obj, list):
        return [remove_ns(x) for x in obj]

    return obj


def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def build_reestr_number_envelope(
    reestr_number: str,
    subsystem_type: str = "RI223",
) -> str:
    """
    Для 223-ФЗ:
      subsystem_type обычно RI223

    Номера вида 32615940337 — это номера закупок 223-ФЗ.
    """

    token = require_env("TOKEN")

    return f"""
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ws="https://int.zakupki.gov.ru/eis-integration/services/getDocsIP">
   <soapenv:Header>
      <individualPerson_token>{token}</individualPerson_token>
   </soapenv:Header>
   <soapenv:Body>
      <ws:getDocsByReestrNumberRequest>
         <index>
            <id>{generate_uid()}</id>
            <createDateTime>{iso_datetime_now()}</createDateTime>
            <mode>PROD</mode>
         </index>
         <selectionParams>
            <subsystemType>{subsystem_type}</subsystemType>
            <reestrNumber>{reestr_number}</reestrNumber>
         </selectionParams>
      </ws:getDocsByReestrNumberRequest>
   </soapenv:Body>
</soapenv:Envelope>
""".strip()


def parse_soap_response(xml_text: str) -> Dict[str, Any]:
    root = etree.fromstring(xml_text.encode("utf-8"))

    namespaces = {
        "soap": "http://schemas.xmlsoap.org/soap/envelope/"
    }

    fault = root.xpath("//soap:Fault", namespaces=namespaces)
    if fault:
        fault_string = fault[0].xpath("faultstring/text()")
        fault_text = fault_string[0] if fault_string else "Unknown SOAP Fault"
        raise RuntimeError(f"SOAP Fault: {fault_text}")

    archive_urls = root.xpath("//*[local-name()='archiveUrl']/text()")
    archive_urls = [x.strip() for x in archive_urls if x and x.strip()]

    ref_id = root.xpath("//*[local-name()='refId']/text()")
    request_id = root.xpath("//*[local-name()='id']/text()")

    return {
        "archiveUrls": archive_urls,
        "archiveUrl": archive_urls[0] if archive_urls else None,
        "refId": ref_id[0] if ref_id else None,
        "requestId": request_id[0] if request_id else None,
    }


def soap_post(envelope_xml: str) -> Dict[str, Any]:
    base_url = require_env("BASE_URL")
    token = require_env("TOKEN")

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "individualPerson_token": token,
    }

    response = session.post(
        base_url,
        data=envelope_xml.encode("utf-8"),
        headers=headers,
        timeout=SOAP_TIMEOUT,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"HTTP {response.status_code}: {response.text[:1000]}"
        )

    parsed = parse_soap_response(response.text)

    return {
        "httpStatus": response.status_code,
        "rawResponse": response.text,
        **parsed,
    }


def get_docs_by_reestr_number(
    reestr_number: str,
    subsystem_type: str = "RI223",
) -> Dict[str, Any]:
    logger.info(
        "Запрос по реестровому номеру | subsystem=%s | number=%s",
        subsystem_type,
        reestr_number,
    )

    envelope = build_reestr_number_envelope(
        reestr_number=reestr_number,
        subsystem_type=subsystem_type,
    )

    return soap_post(envelope)


def download_archive(
    archive_url: str,
    reestr_number: str,
    index: int = 0,
) -> str:
    token = require_env("TOKEN")

    out_path = Path(TMP_DIR) / f"{reestr_number}_{index}.zip"

    headers = {
        "individualPerson_token": token,
    }

    logger.info("Скачивание архива | number=%s | url=%s", reestr_number, archive_url)

    with session.get(
        archive_url,
        headers=headers,
        stream=True,
        timeout=DOWNLOAD_TIMEOUT,
    ) as response:
        if response.status_code >= 400:
            raise RuntimeError(
                f"Download HTTP {response.status_code}: {response.text[:1000]}"
            )

        with open(out_path, "wb") as f:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)

    logger.info("Архив сохранён: %s", out_path)
    return str(out_path)


def inspect_zip(zip_path: str) -> Dict[str, Any]:
    """
    Быстрый просмотр архива:
    - какие XML внутри;
    - какие верхние теги;
    - какие номера закупок найдены внутри.
    """

    result = {
        "zip_path": zip_path,
        "xml_count": 0,
        "xml_files": [],
        "root_tags": [],
        "registration_numbers": [],
        "notice_numbers": [],
        "names": [],
    }

    with zipfile.ZipFile(zip_path, "r") as archive:
        xml_files = [
            name for name in archive.namelist()
            if name.lower().endswith(".xml")
        ]

        result["xml_count"] = len(xml_files)
        result["xml_files"] = xml_files

        for file_name in xml_files:
            try:
                with archive.open(file_name) as f:
                    xml_content = f.read()

                parsed = xmltodict.parse(xml_content)
                parsed = remove_ns(parsed)

                if isinstance(parsed, dict):
                    root_tag = next(iter(parsed.keys()), None)
                    if root_tag:
                        result["root_tags"].append(root_tag)

                text = xml_content.decode("utf-8", errors="ignore")

                # Для purchaseNotice
                for key in ["registrationNumber", "purchaseNoticeNumber"]:
                    # простой regex по XML-тегам после удаления namespace не делаем,
                    # потому что в исходнике могут быть ns-префиксы
                    pass

                # Грубый, но полезный поиск номеров внутри XML
                import re

                nums = re.findall(r">(\d{11})<", text)
                for n in nums:
                    if n not in result["registration_numbers"]:
                        result["registration_numbers"].append(n)

                names = re.findall(
                    r"<[^>]*name[^>]*>(.*?)</[^>]*name>",
                    text,
                    flags=re.IGNORECASE | re.DOTALL,
                )

                for name in names[:5]:
                    clean_name = re.sub(r"\s+", " ", name).strip()
                    if clean_name and clean_name not in result["names"]:
                        result["names"].append(clean_name)

            except Exception as e:
                logger.exception("Ошибка разбора XML %s: %s", file_name, e)

    result["root_tags"] = sorted(set(result["root_tags"]))
    return result


def search_one_number(
    reestr_number: str,
    subsystem_type: str = "RI223",
    download: bool = True,
) -> Dict[str, Any]:
    item = {
        "reestr_number": reestr_number,
        "subsystem_type": subsystem_type,
        "found": False,
        "archive_urls": [],
        "archives": [],
        "error": None,
    }

    try:
        response = get_docs_by_reestr_number(
            reestr_number=reestr_number,
            subsystem_type=subsystem_type,
        )

        archive_urls = response.get("archiveUrls") or []

        item["archive_urls"] = archive_urls
        item["found"] = bool(archive_urls)
        item["refId"] = response.get("refId")
        item["requestId"] = response.get("requestId")
        print(response)
        if not archive_urls:
            logger.warning("Архив не найден | number=%s", reestr_number)
            return item

        if download:
            for i, archive_url in enumerate(archive_urls):
                zip_path = download_archive(
                    archive_url=archive_url,
                    reestr_number=reestr_number,
                    index=i,
                )

                archive_info = inspect_zip(zip_path)

                item["archives"].append(archive_info)

    except Exception as e:
        item["error"] = str(e)
        logger.exception("Ошибка по номеру %s: %s", reestr_number, e)

    return item


def read_numbers_from_txt(path: str) -> List[str]:
    numbers = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            value = line.strip()
            if not value:
                continue

            # если строка из Excel скопирована с табами:
            # 32615940337    11    Название...
            first_col = value.split()[0].strip()

            if first_col.isdigit():
                numbers.append(first_col)

    # дедупликация с сохранением порядка
    seen = set()
    unique_numbers = []

    for n in numbers:
        if n not in seen:
            unique_numbers.append(n)
            seen.add(n)

    return unique_numbers


def search_numbers(
    numbers: List[str],
    subsystem_type: str = "RI223",
    sleep_seconds: float = 1.0,
    out_json: str = "reestr_search_result.json",
) -> List[Dict[str, Any]]:
    results = []

    for idx, number in enumerate(numbers, start=1):
        logger.info("==== %s/%s | %s ====", idx, len(numbers), number)

        result = search_one_number(
            reestr_number=number,
            subsystem_type=subsystem_type,
            download=True,
        )

        results.append(result)

        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4, ensure_ascii=False)

        time.sleep(sleep_seconds)

    found = sum(1 for x in results if x.get("found"))
    not_found = sum(1 for x in results if not x.get("found") and not x.get("error"))
    errors = sum(1 for x in results if x.get("error"))

    logger.info(
        "Готово | всего=%s | найдено=%s | не найдено=%s | ошибок=%s",
        len(results),
        found,
        not_found,
        errors,
    )

    return results


if __name__ == "__main__":
    # Вариант 1: номера прямо в коде
    numbers = [
        "32615940337",
        "32615949258",
        "32615937427",
        "32615942432",
        "32615942428",
        "32615942426",
        "32615945642",
        "32615940504",
        "32615940490",
        "32615940341",
        "32615945789",
        "32615945788",
        "32615940497",
        "32615949261",
        "32615940346",
    ]

    # Вариант 2: читать из файла numbers.txt
    # В файл можно вставить строки из Excel целиком:
    # 32615940337    11    Выполнение ПИР...
    #
    # numbers = read_numbers_from_txt("numbers.txt")

    search_numbers(
        numbers=numbers,
        subsystem_type="RI223",
        sleep_seconds=1.0,
        out_json="reestr_search_result.json",
    )