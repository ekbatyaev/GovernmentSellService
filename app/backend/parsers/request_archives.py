import asyncio
import os
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
import aiofiles
import httpx
import xmltodict
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.settings import settings, logger,MOSCOW_TZ

async_client = httpx.AsyncClient(timeout=30)

# ---------------------------------------------------------------------------
# Конфигурация клиента / параллелизма
# ---------------------------------------------------------------------------

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Referer": "https://zakupki.gov.ru/",
    "Accept": "*/*",
}
# Проставляем дефолтные заголовки один раз на общий async_client.
async_client.headers.update(DEFAULT_HEADERS)

class _NotFound(Exception):
    """Служебный сигнал 404 — не ретраим, просто сообщаем вызывающему коду."""


def _is_retryable_http_error(exc: BaseException) -> bool:
    """Ретраим только сетевые сбои и 429/5xx. Остальные 4xx повторять бессмысленно."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return isinstance(exc, httpx.RequestError)


def _log_retry(retry_state) -> None:
    exc = retry_state.outcome.exception()
    logger.warning(
        "Повтор запроса (попытка %d) после ошибки: %s",
        retry_state.attempt_number,
        exc,
    )

def parse_soap_response(xml_text: str) -> dict:
    data = xmltodict.parse(xml_text)
    main_info_body = data.get("soap:Envelope", {}).get("soap:Body", {}).get(
        "ns2:getDocsByOrgRegionResponse", {}
    )

    data_info = main_info_body.get("dataInfo", {})
    archive_urls = data_info.get("archiveUrl", [])

    if isinstance(archive_urls, str):
        archive_urls = [archive_urls]

    return {"archive_urls": archive_urls}


# ---------------------------------------------------------------------------
# SOAP-запросы
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception(_is_retryable_http_error),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
    before_sleep=_log_retry,
    reraise=True,
)
async def soap_post(envelope_xml: str) -> dict:
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "individualPerson_token": settings.token,
    }

    response = await async_client.post(
        settings.base_url,
        content=envelope_xml,
        headers=headers,
        timeout=settings.soap_timeout,
    )
    response.raise_for_status()

    parsed = parse_soap_response(response.text)
    return {"httpStatus": response.status_code, **parsed}


async def get_docs_by_region(
    org_region: str,
    document_type: str,
    exact_date: str | None = None,
    subsystem_type: str = "RI223",
) -> dict:
    exact_date = exact_date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    envelope = f"""
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ws="http://zakupki.gov.ru/fz44/get-docs-ip/ws">
   <soapenv:Header>
      <individualPerson_token>{settings.token}</individualPerson_token>
   </soapenv:Header>
   <soapenv:Body>
      <ws:getDocsByOrgRegionRequest>
         <index>
            <id>{str(uuid.uuid4())}</id>
            <createDateTime>{datetime.now(MOSCOW_TZ).strftime("%Y-%m-%dT%H:%M:%S")}</createDateTime>
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
    return await soap_post(envelope)


# ---------------------------------------------------------------------------
# Скачивание архивов
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception(_is_retryable_http_error),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    before_sleep=_log_retry,
    reraise=True,
)
async def _stream_download(
    url: str, params: dict | None, headers: dict, path: str
) -> None:
    async with async_client.stream(
        "GET", url, params=params, headers=headers, timeout=settings.download_timeout
    ) as response:
        if response.status_code == 404:
            raise _NotFound()
        response.raise_for_status()

        async with aiofiles.open(path, "wb") as f:
            async for chunk in response.aiter_bytes(1024 * 1024):
                if chunk:
                    await f.write(chunk)


async def download_archive_from_result(
    archive_url: str,
    out_file: str | None = None,
) -> str | None:
    parsed = urlparse(archive_url)
    params = parse_qs(parsed.query)
    doc_request_uid = params.get("docRequestUid", [None])[0]
    compound_uid = params.get("compoundUid", [None])[0]

    headers = {"individualPerson_token": settings.token}

    if archive_url:
        url = archive_url
        req_params = None
    else:
        if not doc_request_uid or not compound_uid:
            raise ValueError("Archive info missing (docRequestUid/compoundUid)")
        url = settings.download_url
        req_params = {"docRequestUid": doc_request_uid, "compoundUid": compound_uid}

    if not out_file:
        out_file = f"{compound_uid or str(uuid.uuid4())}.zip"

    path = os.path.abspath(os.path.join(settings.tmp_dir, out_file))

    async with asyncio.Semaphore(settings.max_concurrent_semaphore):
        try:
            logger.info("Скачивание архива %s", out_file)
            await _stream_download(url, req_params, headers, path)
            logger.info("Архив сохранён: %s", path)
            return path

        except _NotFound:
            logger.warning(
                "Архив не найден (404): %s, пропускаем",
                archive_url or f"{url}?{req_params}",
            )
            return None

        except httpx.HTTPStatusError as e:
            # Сюда попадают только НЕретраящиеся статусы (не 429/5xx) — see _is_retryable_http_error.
            logger.error(
                "HTTP ошибка %d, повторять бессмысленно: %s",
                e.response.status_code,
                e,
            )
            return None

        except httpx.RequestError as e:
            logger.error("Сетевая ошибка после всех попыток: %s", e)
            return None

        except Exception:
            logger.exception("Неожиданная ошибка при скачивании %s", out_file)
            return None


async def download_archives(archive_urls: list[str]) -> list[str]:
    """
    Параллельно скачивает несколько архивов (ограничено DOWNLOAD_SEMAPHORE).
    Возвращает список путей к успешно скачанным файлам (None-результаты отфильтрованы).
    """
    results = await asyncio.gather(
        *(download_archive_from_result(url) for url in archive_urls)
    )
    return [path for path in results if path]