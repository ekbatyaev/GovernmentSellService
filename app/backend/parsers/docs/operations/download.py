from pathlib import Path
from tenacity import retry, retry_if_exception, stop_after_attempt
from app.backend.parsers.docs.config import (get_client, filestore_limiter, fallback_wait,
                                             CHUNK_SIZE, download_semaphore)
from app.backend.parsers.docs.functions import ensure_dir, format_log_kv, safe_filename, guess_extension_from_magic
from app.backend.parsers.docs.operations.regex.rar import is_rar_part_filename
from app.backend.parsers.docs.schemas import Entry
from app.settings import logger
from urllib.parse import unquote, urlparse
from typing import Optional
import mimetypes
import aiofiles
import httpx
import asyncio
import re
import time
import uuid


class InvalidDownloadContentError(Exception):
    """Сервер вернул некорректное содержимое документа."""


def _guess_filename(response: httpx.Response, url: str, fallback: str = "downloaded_file") -> str:
    cd = response.headers.get("Content-Disposition", "")
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, flags=re.IGNORECASE)
    if match:
        return safe_filename(unquote(match.group(1)))

    name = Path(unquote(urlparse(str(response.url) or url).path)).name
    if name:
        return safe_filename(name)

    content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    return safe_filename(fallback + (mimetypes.guess_extension(content_type) or ""))


def _is_retryable_download_error(exc: BaseException) -> bool:
    """
    Повторяем 429, 5xx, сетевые сбои
    и получение некорректного содержимого.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500

    return isinstance(
        exc,
        (
            httpx.TransportError,
            InvalidDownloadContentError,
        ),
    )


def _wait_retry_after(retry_state) -> float:
    """При 429 ждём столько, сколько просит сервер в Retry-After, иначе растущая пауза."""
    exc = retry_state.outcome.exception()
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        retry_after = exc.response.headers.get("Retry-After", "")
        if retry_after.isdigit():
            return min(int(retry_after), 300)
    return fallback_wait(retry_state)


def _log_download_retry(retry_state) -> None:
    logger.warning(
        "DOWNLOAD RETRY | %s",
        format_log_kv(
            task_id=retry_state.kwargs.get("task_id"),
            url=retry_state.kwargs.get("url"),
            attempt=retry_state.attempt_number,
            sleep=f"{retry_state.next_action.sleep:.0f}s",
            error=str(retry_state.outcome.exception()),
        ),
    )


@retry(
    retry=retry_if_exception(_is_retryable_download_error),
    stop=stop_after_attempt(5),
    wait=_wait_retry_after,
    before_sleep=_log_download_retry,
    reraise=True,
)
async def download_file(
    url: str,
    download_dir: str | Path,
    filename: Optional[str] = None,
    task_id: str | None = None,
) -> Path:
    download_dir = ensure_dir(download_dir)
    client = await get_client()
    started = time.perf_counter()

    temp_path: Path | None = None
    expected_size: str | None = None
    written = 0

    logger.info(
        "DOWNLOAD START | %s",
        format_log_kv(
            task_id=task_id,
            url=url,
            filename=filename,
            download_dir=download_dir,
        ),
    )

    try:
        async with download_semaphore:
            async with filestore_limiter:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()

                    path = download_dir / safe_filename(
                        filename or _guess_filename(response, url)
                    )

                    # Временный файл с коротким уникальным именем
                    temp_path = download_dir / (
                        f".{uuid.uuid4().hex}.part"
                    )

                    content_type = (
                        response.headers.get("Content-Type") or ""
                    ).split(";")[0].strip().lower()

                    content_encoding = (
                        response.headers.get("Content-Encoding") or ""
                    ).strip().lower()

                    expected_size = (
                        response.headers.get("Content-Length")
                        if content_encoding in ("", "identity")
                        else None
                    )

                    async with aiofiles.open(temp_path, "wb") as f:
                        async for chunk in response.aiter_bytes(
                            CHUNK_SIZE
                        ):
                            if chunk:
                                await f.write(chunk)
                                written += len(chunk)

        # Проверяем размер скачанного документа
        if expected_size is not None:
            try:
                expected = int(expected_size)
            except ValueError:
                expected = None

            if expected is not None and written != expected:
                raise InvalidDownloadContentError(
                    f"Файл скачан не полностью: "
                    f"expected={expected}, got={written}"
                )

        # Проверяем наличие содержимого
        if (
            not temp_path.exists()
            or temp_path.stat().st_size == 0
        ):
            raise InvalidDownloadContentError(
                "Файл не скачан или пустой"
            )

        # Читаем первые 4096 байт
        async with aiofiles.open(temp_path, "rb") as f:
            head = await f.read(4096)

        # Проверяем, не вернул ли сервер HTML
        normalized_head = head.lstrip(
            b"\xef\xbb\xbf \t\r\n"
        ).lower()

        is_probably_html = (
            normalized_head.startswith(b"<!doctype html")
            or normalized_head.startswith(b"<html")
            or normalized_head.startswith(b"<head")
            or normalized_head.startswith(b"<body")
            or (
                content_type in {
                    "text/html",
                    "application/xhtml+xml",
                }
                and (
                    b"<html" in normalized_head
                    or b"<body" in normalized_head
                )
            )
        )

        # Настоящий HTML-документ допускаем:
        # анализатор впоследствии его пропустит.
        if (
            is_probably_html
            and path.suffix.lower() not in {".html", ".htm"}
        ):
            logger.warning(
                "DOWNLOAD HTML RESPONSE | %s",
                format_log_kv(
                    task_id=task_id,
                    url=url,
                    filename=path.name,
                    content_type=content_type,
                    size_bytes=written,
                ),
            )

            raise InvalidDownloadContentError(
                "Получен HTML вместо запрошенного документа"
            )

        # Определяем настоящее расширение файла
        magic_ext = guess_extension_from_magic(
            head, path.name
        )

        if (
            magic_ext
            and path.suffix.lower() != magic_ext
            and not is_rar_part_filename(path.name)
        ):
            path = path.with_suffix(magic_ext)

        # Только проверенный файл получает окончательное имя
        temp_path.replace(path)
        temp_path = None

        logger.info(
            "DOWNLOAD DONE | %s",
            format_log_kv(
                task_id=task_id,
                url=url,
                saved_as=path.name,
                size_bytes=written,
                expected_size=expected_size,
                elapsed=f"{time.perf_counter() - started:.3f}s",
            ),
        )

        return path

    finally:
        # Удаляем временный файл при любой ошибке
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError as e:
                logger.warning(
                    "DOWNLOAD CLEANUP ERROR | %s",
                    format_log_kv(
                        task_id=task_id,
                        path=temp_path,
                        error=str(e),
                    ),
                )


async def download_multipart_rar(parts: list[Entry], work_dir: Path, task_id: str | None = None) -> Path:
    logger.info("MULTIPART_RAR START | %s", format_log_kv(task_id=task_id, parts=len(parts)))

    try:
        async with asyncio.TaskGroup() as tg:
            tasks = [
                tg.create_task(download_file(
                    url=item.doc.url,
                    download_dir=work_dir,
                    filename=item.doc.filename,
                    task_id=task_id,
                ))
                for item in parts
            ]
    except ExceptionGroup as eg:
        raise eg.exceptions[0]

    downloaded = sorted(
        ((task.result(), item) for task, item in zip(tasks, parts)),
        key=lambda x: x[1].part_num or 0,
    )

    chosen = next((path for path, item in downloaded if item.is_start), downloaded[0][0])

    logger.info(
        "MULTIPART_RAR DONE | %s",
        format_log_kv(task_id=task_id, chosen=chosen.name, total_parts=len(downloaded)),
    )
    return chosen
