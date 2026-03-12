import os
import uuid
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

import requests
from dotenv import load_dotenv
from lxml import etree


load_dotenv()

BASE_URL = os.getenv("BASE_URL")
TOKEN = os.getenv("TOKEN")
DOWNLOAD_URL = os.getenv("DOWNLOAD_URL")

SOAP_TIMEOUT = int(os.getenv("SOAP_TIMEOUT", "30"))
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "60"))

TMP_DIR = "tmp"

os.makedirs(TMP_DIR, exist_ok=True)

# ------------------------------------------------
# Logging
# ------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

# ------------------------------------------------
# HTTP session (reuse connection)
# ------------------------------------------------

session = requests.Session()


# ============================================================
# Utils
# ============================================================

def generate_uid() -> str:
    return str(uuid.uuid4())


def iso_datetime_now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def iso_date_today_minus(days: int = 1) -> str:
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")


# ============================================================
# SOAP Response parsing
# ============================================================

def parse_soap_response(xml_text: str) -> dict:

    root = etree.fromstring(xml_text.encode())

    namespaces = {"soap": "http://schemas.xmlsoap.org/soap/envelope/"}

    fault = root.xpath("//soap:Fault", namespaces=namespaces)

    if fault:
        fault_string = fault[0].xpath("faultstring/text()")
        raise Exception(f"SOAP Fault: {fault_string[0] if fault_string else 'Unknown'}")

    doc_uid = root.xpath("//*[local-name()='docRequestUid']/text()")
    compound_uid = root.xpath("//*[local-name()='compoundUid']/text()")

    archive_url = root.xpath("//*[local-name()='archiveUrl']/text()")
    archive_url = archive_url[0].strip() if archive_url else None

    doc_request_uid = doc_uid[0] if doc_uid else None
    compound_uid = compound_uid[0] if compound_uid else None

    if archive_url and (not doc_request_uid or not compound_uid):

        qs = parse_qs(urlparse(archive_url).query)

        doc_request_uid = doc_request_uid or (qs.get("docRequestUid") or [None])[0]
        compound_uid = compound_uid or (qs.get("compoundUid") or [None])[0]

    return {
        "archiveUrl": archive_url,
        "docRequestUid": doc_request_uid,
        "compoundUid": compound_uid
    }


# ============================================================
# SOAP request
# ============================================================

def soap_post(envelope_xml: str) -> dict:

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "individualPerson_token": TOKEN
    }

    response = session.post(
        BASE_URL,
        data=envelope_xml,
        headers=headers,
        timeout=SOAP_TIMEOUT
    )

    response.raise_for_status()

    parsed = parse_soap_response(response.text)

    return {
        "httpStatus": response.status_code,
        **parsed
    }


# ============================================================
# Get docs by region
# ============================================================

def get_docs_by_region(
    org_region: str,
    document_type: str,
    exact_date: str | None = None,
    subsystem_type: str = "RI223"
) -> dict:

    exact_date = exact_date or iso_date_today_minus()

    envelope = f"""
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ws="http://zakupki.gov.ru/fz44/get-docs-ip/ws">
   <soapenv:Header>
      <individualPerson_token>{TOKEN}</individualPerson_token>
   </soapenv:Header>
   <soapenv:Body>
      <ws:getDocsByOrgRegionRequest>
         <index>
            <id>{generate_uid()}</id>
            <createDateTime>{iso_datetime_now()}</createDateTime>
            <mode>PROD</mode>
         </index>
         <selectionParams>
            <orgRegion>{org_region}</orgRegion>
            <subsystemType>{subsystem_type}</subsystemType>
            <documentType223>{document_type}</documentType223>
            <periodInfo>
               <exactDate>{exact_date}</exactDate>
            </periodInfo>
         </selectionParams>
      </ws:getDocsByOrgRegionRequest>
   </soapenv:Body>
</soapenv:Envelope>
"""

    logger.info("Запрос закупок | region=%s date=%s", org_region, exact_date)

    return soap_post(envelope)


# ============================================================
# Download archive
# ============================================================

def download_archive_from_result(result: dict, out_file: str | None = None) -> str:

    archive_url = result.get("archiveUrl")
    doc_request_uid = result.get("docRequestUid")
    compound_uid = result.get("compoundUid")

    headers = {"individualPerson_token": TOKEN}

    if archive_url:
        url = archive_url
        params = None
    else:

        if not doc_request_uid or not compound_uid:
            raise ValueError("Archive info missing")

        url = DOWNLOAD_URL
        params = {
            "docRequestUid": doc_request_uid,
            "compoundUid": compound_uid
        }

    out_file = out_file or f"{compound_uid}.zip"

    tmp_path = os.path.join(TMP_DIR, out_file)

    path = os.path.join(os.path.abspath(os.getcwd()), tmp_path)

    logger.info("Скачивание архива %s", out_file)

    with session.get(
        url,
        params=params,
        headers=headers,
        stream=True,
        timeout=DOWNLOAD_TIMEOUT
    ) as r:

        r.raise_for_status()

        with open(path, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                f.write(chunk)

    logger.info("Архив сохранён: %s", path)

    return path


# ============================================================
# Example
# ============================================================

if __name__ == "__main__":

    result = get_docs_by_region(
        org_region="77",
        document_type="purchaseNotice",
        exact_date="2025-02-16"
    )

    logger.info("HTTP статус: %s", result["httpStatus"])

    archive = download_archive_from_result(result)

    logger.info("Архив скачан: %s", archive)