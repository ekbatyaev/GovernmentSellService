import os
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

import requests
from dotenv import load_dotenv
from lxml import etree


# ============================================================
# Config (.env)
# ============================================================
load_dotenv()

BASE_URL = os.getenv("BASE_URL")  # SOAP endpoint
TOKEN = os.getenv("TOKEN")        # individualPerson_token
DOWNLOAD_URL = os.getenv(
    "DOWNLOAD_URL"
)

SOAP_TIMEOUT = int(os.getenv("SOAP_TIMEOUT", "30"))
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "60"))


# ============================================================
# Utils
# ============================================================
def generate_uid() -> str:
    return str(uuid.uuid4())


def iso_datetime_now(with_ms: bool = False) -> str:
    if with_ms:
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def iso_date_today_minus(days: int = 1) -> str:
    """YYYY-MM-DD (удобно для exactDate в запросе по региону)."""
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")


# ============================================================
# SOAP Response parsing
# ============================================================
def parse_soap_response(xml_text: str) -> dict:
    """
    Достаём данные для скачивания архива:
    - archiveUrl (если есть)
    - docRequestUid, compoundUid (могут быть тегами или в query archiveUrl)
    """
    try:
        root = etree.fromstring(xml_text.encode("utf-8"))
    except etree.XMLSyntaxError as e:
        raise Exception(f"XML parse error: {e}")

    namespaces = {"soap": "http://schemas.xmlsoap.org/soap/envelope/"}

    # SOAP Fault check
    fault = root.xpath("//soap:Fault", namespaces=namespaces)
    if fault:
        fault_string = fault[0].xpath("faultstring/text()")
        raise Exception(f"SOAP Fault: {fault_string[0] if fault_string else 'Unknown fault'}")

    # 1) Если API вернул отдельные теги docRequestUid/compoundUid
    doc_uid = root.xpath("//*[local-name()='docRequestUid']/text()")
    compound_uid = root.xpath("//*[local-name()='compoundUid']/text()")

    # 2) Частый вариант: всё лежит в archiveUrl
    archive_url = root.xpath("//*[local-name()='archiveUrl']/text()")
    archive_url = archive_url[0].strip() if archive_url else None

    doc_request_uid = doc_uid[0] if doc_uid else None
    comp_uid = compound_uid[0] if compound_uid else None

    if archive_url and (not doc_request_uid or not comp_uid):
        qs = parse_qs(urlparse(archive_url).query)
        doc_request_uid = doc_request_uid or (qs.get("docRequestUid") or [None])[0]
        comp_uid = comp_uid or (qs.get("compoundUid") or [None])[0]

    return {
        "archiveUrl": archive_url,
        "docRequestUid": doc_request_uid,
        "compoundUid": comp_uid,
    }


# ============================================================
# Low-level SOAP POST (общая функция)
# ============================================================
def soap_post(envelope_xml: str) -> dict:
    if not BASE_URL:
        raise ValueError("BASE_URL is not set (put it into .env)")
    if not TOKEN:
        raise ValueError("TOKEN is not set (put it into .env)")

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        # Чтобы соответствовать Postman (токен и в SOAP Header, и как HTTP header)
        "individualPerson_token": TOKEN,
    }

    resp = requests.post(
        BASE_URL,
        data=envelope_xml.encode("utf-8"),
        headers=headers,
        timeout=SOAP_TIMEOUT,
    )
    resp.raise_for_status()

    parsed = parse_soap_response(resp.text)
    return {
        "httpStatus": resp.status_code,
        "rawXml": resp.text,
        **parsed,
    }


# ============================================================
# 1) Получение по региону
# ============================================================
def get_docs_by_region(
    org_region: str,
    document_type: str,
    exact_date: str | None = None,
    subsystem_type: str = "PRIZ",
    mode: str = "PROD",
    request_id: str | None = None,
    create_datetime: str | None = None,
) -> dict:
    """
    ws:getDocsByOrgRegionRequest

    Используйте, когда вы ищете "выгрузку по условиям":
      регион + тип документа + дата.
    """
    request_id = request_id or generate_uid()
    create_datetime = create_datetime or iso_datetime_now()
    exact_date = exact_date or iso_date_today_minus(1)

    envelope = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ws="http://zakupki.gov.ru/fz44/get-docs-ip/ws">
   <soapenv:Header>
      <individualPerson_token>{TOKEN}</individualPerson_token>
   </soapenv:Header>
   <soapenv:Body>
      <ws:getDocsByOrgRegionRequest>
         <index>
            <id>{request_id}</id>
            <createDateTime>{create_datetime}</createDateTime>
            <mode>{mode}</mode>
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
</soapenv:Envelope>"""

    return soap_post(envelope)


# ============================================================
# 2) Получение по номеру (реестровому)
# ============================================================
def get_docs_by_reestr_number(
    reestr_number: str,
    subsystem_type: str = "RI223",
    mode: str = "PROD",
    request_id: str | None = None,
    create_datetime: str | None = None,
) -> dict:
    """
    ws:getDocsByReestrNumberRequest

    Используйте, когда у вас уже есть точный идентификатор:
      reestrNumber (номер реестра) + subsystemType.
    """
    request_id = request_id or generate_uid()
    create_datetime = create_datetime or iso_datetime_now()

    envelope = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ws="http://zakupki.gov.ru/fz44/get-docs-ip/ws">
   <soapenv:Header>
      <individualPerson_token>{TOKEN}</individualPerson_token>
   </soapenv:Header>
   <soapenv:Body>
      <ws:getDocsByReestrNumberRequest>
         <index>
            <id>{request_id}</id>
            <createDateTime>{create_datetime}</createDateTime>
            <mode>{mode}</mode>
         </index>
         <selectionParams>
            <subsystemType>{subsystem_type}</subsystemType>
            <reestrNumber>{reestr_number}</reestrNumber>
         </selectionParams>
      </ws:getDocsByReestrNumberRequest>
   </soapenv:Body>
</soapenv:Envelope>"""

    return soap_post(envelope)


# ============================================================
# Download archive (общий для обоих сценариев)
# ============================================================
def download_archive_from_result(result: dict, out_file: str | None = None) -> str:
    """
    Скачивание архива на основе результата get_docs_by_region / get_docs_by_reestr_number.

    Приоритет:
      1) archiveUrl (прямая ссылка)
      2) DOWNLOAD_URL + docRequestUid + compoundUid
    """
    if not TOKEN:
        raise ValueError("TOKEN is not set (put it into .env)")

    archive_url = result.get("archiveUrl")
    doc_request_uid = result.get("docRequestUid")
    compound_uid = result.get("compoundUid")

    headers = {"individualPerson_token": TOKEN}

    if archive_url:
        url = archive_url
        params = None
        if not compound_uid:
            qs = parse_qs(urlparse(archive_url).query)
            compound_uid = (qs.get("compoundUid") or [None])[0]
    else:
        if not doc_request_uid or not compound_uid:
            raise ValueError("No archiveUrl and no docRequestUid/compoundUid in result.")
        url = DOWNLOAD_URL
        params = {"docRequestUid": doc_request_uid, "compoundUid": compound_uid}

    if not out_file:
        out_file = f"{compound_uid or 'archive'}.zip"

    with requests.get(url, params=params, headers=headers, timeout=DOWNLOAD_TIMEOUT, stream=True) as r:
        r.raise_for_status()
        with open(out_file, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    return out_file


# ============================================================
# Example usage (явно разделено: по региону / по номеру)
# ============================================================
if __name__ == "__main__":
    # -------------------------
    # A) Сценарий: получить по региону и скачать
    # -------------------------
    region_result = get_docs_by_region(
        org_region="77",
        document_type = "purchaseNotice",
        exact_date="2025-12-16",
        subsystem_type="RI223",
    )

    print("REGION HTTP:", region_result["httpStatus"])
    print("REGION archiveUrl:", region_result["archiveUrl"])
    saved = download_archive_from_result(region_result)
    print("REGION saved:", saved)

    # -------------------------
    # B) Сценарий: получить по реестровому номеру и скачать
    # -------------------------
    # number_result = get_docs_by_reestr_number(
    #     reestr_number="32515333208",
    #     subsystem_type="RI223",
    # )
    # print("NUMBER HTTP:", number_result["httpStatus"])
    # print("NUMBER archiveUrl:", number_result["archiveUrl"])
    # saved = download_archive_from_result(number_result)
    # print("NUMBER saved:", saved)
