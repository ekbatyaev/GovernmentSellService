import os
import uuid
import logging
from datetime import datetime, timedelta
import requests
import xmltodict
from dotenv import load_dotenv
from urllib.parse import urlparse, parse_qs

load_dotenv()

BASE_URL = os.getenv("BASE_URL")
TOKEN = os.getenv("TOKEN")
DOWNLOAD_URL = os.getenv("DOWNLOAD_URL")

SOAP_TIMEOUT = int(os.getenv("SOAP_TIMEOUT", "30"))
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "60"))

TMP_DIR = os.getenv("TMP_DIR", "tmp")
os.makedirs(TMP_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def build_session() -> requests.Session:
    session = requests.Session()

    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )

    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=20,
        pool_maxsize=20
    )

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Referer": "https://zakupki.gov.ru/",
        "Accept": "*/*",
    })

    return session

session = build_session()


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def generate_uid() -> str:
    return str(uuid.uuid4())


def iso_datetime_now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def iso_date_today_minus(days: int = 1) -> str:
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

def parse_soap_response(xml_text: str) -> dict:
    data = xmltodict.parse(xml_text)
    main_info_body = data.get('soap:Envelope', {}).get("soap:Body", {}).get("ns2:getDocsByOrgRegionResponse", {})

    data_info = main_info_body.get("dataInfo", {})
    archive_urls = data_info.get('archiveUrl', [])

    if isinstance(archive_urls, str):
        archive_urls = [archive_urls]

    return {"archive_urls": archive_urls}


def soap_post(envelope_xml: str) -> dict:
    _require_env("BASE_URL")
    _require_env("TOKEN")

    headers = {"Content-Type": "text/xml; charset=utf-8", "individualPerson_token": TOKEN}

    response = session.post(BASE_URL, data=envelope_xml, headers=headers, timeout=SOAP_TIMEOUT)

    response.raise_for_status()

    parsed = parse_soap_response(response.text)
    return {"httpStatus": response.status_code, **parsed}

def get_docs_by_region(
    org_region: str,
    document_type: str,
    exact_date: str | None = None,
    subsystem_type: str = "RI223",
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
""".strip()

    logger.info("Запрос закупок | region=%s date=%s", org_region, exact_date)
    return soap_post(envelope)


def download_archive_from_result(archive_url, out_file: str | None = None) -> str:
    _require_env("TOKEN")
    _require_env("DOWNLOAD_URL")

    parsed = urlparse(archive_url)

    params = parse_qs(parsed.query)

    doc_request_uid = params.get("docRequestUid", [None])[0]

    compound_uid = params.get("compoundUid", [None])[0]

    headers = {"individualPerson_token": TOKEN}

    if archive_url:
        url = archive_url
        params = None
    else:

        if not doc_request_uid or not compound_uid:
            raise ValueError(f"Archive info missing (docRequestUid/compoundUid), httpStatus: {result.get("httpStatus")}")
        url = DOWNLOAD_URL
        params = {"docRequestUid": doc_request_uid, "compoundUid": compound_uid}

    if not out_file:
        out_file = f"{compound_uid or generate_uid()}.zip"

    path = os.path.abspath(os.path.join(TMP_DIR, out_file))

    logger.info("Скачивание архива %s", out_file)

    with session.get(url, params=params, headers=headers, stream=True, timeout=DOWNLOAD_TIMEOUT) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)

    logger.info("Архив сохранён: %s", path)
    return path