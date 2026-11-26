from pathlib import Path
from app.backend.parsers.docs.config import (SUPPORTED_EXTENSIONS, extract_semaphore,
                                             SOFFICE_BIN, LEGACY_OFFICE_EXTENSIONS, EXT_TO_MIME)
from app.backend.parsers.docs.functions import format_log_kv
from kreuzberg import (
    extract_bytes,
    extract_file,
    render_pdf_page
)
from app.backend.parsers.docs.config import (PDF_TITLE_PAGE_RENDER_DPI, OCR_CONFIG,
                                             MAX_PDF_PAGES, MAX_TEXT_CHARS, MAX_TEXT_FILE_BYTES,
                                             PDF_PAGES_CONFIG, PDF_TITLE_PAGE_MIN_TEXT_CHARS,
                                             PDF_TITLE_PAGE_IMAGE_TEXT_ENABLED)
from app.backend.parsers.docs.operations.extractors.functions import (is_binary_bytes, detect_encoding,
                                                                      detect_true_extension, convert_legacy_batch)
from app.backend.parsers.docs.schemas import ExtractInfo
from app.settings import logger
import asyncio
import time
import shutil


class SkipDocument(Exception):
    """Документ намеренно пропущен."""


def _read_text_file(path: Path) -> str:
    """
    Своё чтение .txt: kreuzberg не определяет cp1251 и отдаёт мойбейк.
    """
    size = path.stat().st_size
    if size > MAX_TEXT_FILE_BYTES:
        raise ValueError(f"TXT слишком большой: {size} байт")

    data = path.read_bytes()
    if is_binary_bytes(data):
        raise ValueError("Файл бинарный, это не txt")

    return data.decode(detect_encoding(data), errors="replace").strip()


async def _ocr_pdf_page(path: Path, page_index: int = 0, task_id: str | None = None) -> str:
    """OCR ТОЛЬКО указанной страницы: рендерим её в PNG и распознаём."""
    started = time.perf_counter()
    try:
        png = await asyncio.to_thread(
            render_pdf_page, str(path), page_index, dpi=PDF_TITLE_PAGE_RENDER_DPI
        )
        result = await extract_bytes(png, "image/png", config=OCR_CONFIG)
        text = (result.content or "").strip()

        logger.info(
            "PDF TITLE OCR DONE | %s",
            format_log_kv(
                task_id=task_id,
                path=path.name,
                text_len=len(text),
                elapsed=f"{time.perf_counter() - started:.3f}s",
            ),
        )
        return text

    except Exception as e:
        logger.warning(
            "PDF TITLE OCR ERROR | %s",
            format_log_kv(task_id=task_id, path=path.name, error=str(e)),
        )
        return ""


async def _extract_pdf_title_text(path: Path, task_id: str | None = None) -> str:
    """
    Читаем только титульный лист: сначала текстовый слой первой страницы,
    при коротком результате — OCR первой страницы.
    """
    result = await extract_file(path, config=PDF_PAGES_CONFIG)
    pages = getattr(result, "pages", None) or []
    text = ((pages[0].get("content") if pages else result.content) or "").strip()

    if len(text) >= PDF_TITLE_PAGE_MIN_TEXT_CHARS:
        return text

    logger.info(
        "PDF TITLE TEXT_LAYER SHORT | %s",
        format_log_kv(task_id=task_id, path=path.name, text_len=len(text)),
    )

    if PDF_TITLE_PAGE_IMAGE_TEXT_ENABLED:
        ocr_text = await _ocr_pdf_page(path, 0, task_id)
        if ocr_text:
            return ocr_text

    return text


async def _extract_pdf_full_text(path: Path, task_id: str | None = None) -> str:
    """
    Полный текст PDF с теми же лимитами, что были в исходных (неиспользовавшихся)
    read_pdf_file_pypdf/pymupdf: не больше MAX_PDF_PAGES страниц и MAX_TEXT_CHARS символов.
    """
    result = await extract_file(path, config=PDF_PAGES_CONFIG)
    pages = getattr(result, "pages", None) or []

    if not pages:
        return (result.content or "").strip()[:MAX_TEXT_CHARS]

    parts: list[str] = []
    total = 0

    for page in pages[:MAX_PDF_PAGES]:
        text = (page.get("content") or "").strip()
        if not text:
            continue

        parts.append(text)
        total += len(text)
        if total >= MAX_TEXT_CHARS:
            break

    logger.info(
        "PDF FULL READ | %s",
        format_log_kv(
            task_id=task_id, path=path.name,
            pages_total=len(pages), pages_read=len(parts), text_len=total,
        ),
    )
    return "\n".join(parts).strip()[:MAX_TEXT_CHARS]


async def _extract_text(
    path: Path,
    task_id: str | None = None,
    full_text: bool = False,
    converted_legacy: Path | None = None,
) -> str:
    """
    Единая точка извлечения текста. Бросает ValueError на неподдерживаемый формат.

    full_text=False у PDF означает «только титульный лист» — это оптимизация ровно
    под поиск проектировщика. Для всего остального (протоколы, ТЗ) нужен full_text=True,
    иначе в модель и в поиск слов-маячков уйдёт одна первая страница.

    converted_legacy — путь к OOXML-версии для legacy-форматов (.doc/.xls/.ppt/.odt),
    подготовленный вызовом convert_legacy_batch(). Если None и soffice доступен —
    конвертируем одиночным вызовом; если soffice недоступен — читаем как есть,
    битость вычистит salvage в extract_one.
    """
    ext = path.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        logger.warning(f"Найден неподдерживаемый формат: {ext or path.name}")

    # реальный тип по содержимому; роутим по нему
    true_ext = await asyncio.to_thread(detect_true_extension, path)
    if true_ext not in SUPPORTED_EXTENSIONS:
        raise SkipDocument(f"Пропущен неподдерживаемый формат: {true_ext} ({path.name})")

    async with extract_semaphore:
        # legacy Office читаем через конвертированный OOXML
        if true_ext in LEGACY_OFFICE_EXTENSIONS:
            source = converted_legacy
            if source is None and SOFFICE_BIN:
                single_map, single_tmp = await convert_legacy_batch([path], task_id)
                source = single_map.get(path)
                if source is None:
                    shutil.rmtree(single_tmp, ignore_errors=True)
            if source is not None:
                result = await extract_file(source)
                return (result.content or "").strip()
            logger.warning(
                "LEGACY DIRECT READ | %s",
                format_log_kv(task_id=task_id, path=path.name),
            )

        if true_ext == ".txt":
            return await asyncio.to_thread(_read_text_file, path)

        if true_ext == ".pdf":
            if full_text:
                return await _extract_pdf_full_text(path, task_id)
            return await _extract_pdf_title_text(path, task_id)

        result = await extract_file(path, mime_type=EXT_TO_MIME.get(true_ext))
        return (result.content or "").strip()


async def extract_one(
    path: Path, task_id: str | None, full_text: bool = False,
    converted_legacy: Path | None = None
) -> ExtractInfo:
    """Возвращает (path, text, error). Исключения не пробрасывает."""
    started = time.perf_counter()
    try:
        text = await _extract_text(path, task_id=task_id, full_text=full_text,
                                   converted_legacy=converted_legacy)
        elapsed = time.perf_counter() - started

        if not text.strip():
            logger.warning(
                "READ_FILE EMPTY | %s",
                format_log_kv(task_id=task_id, filename=path.name, elapsed=f"{elapsed:.3f}s"),
            )
            return ExtractInfo(path=path,
                               text=None,
                               error="Текст не извлечен")

        logger.info(
            "READ_FILE DONE | %s",
            format_log_kv(
                task_id=task_id, filename=path.name, ext=path.suffix.lower(),
                text_len=len(text), elapsed=f"{elapsed:.3f}s",
            ),
        )
        return ExtractInfo(path=path,
                           text=text,
                           error=None)

    except SkipDocument as e:
        logger.info(
            "READ_FILE SKIPPED | %s",
            format_log_kv(
                task_id=task_id,
                filename=path.name,
                reason=str(e),
            ),
        )

        return ExtractInfo(
            path=path,
            text=None,
            error=None,
            skipped=True
        )

    except ValueError as e:
        logger.warning(
            "READ_FILE NO_TEXT | %s",
            format_log_kv(task_id=task_id, filename=path.name, error=str(e)),
        )
        return ExtractInfo(path=path,
                           text=None,
                           error=str(e))

    except Exception as e:
        logger.exception(
            "READ_FILE ERROR | %s",
            format_log_kv(task_id=task_id, filename=path.name, error=str(e)),
        )
        return ExtractInfo(path=path,
                           text=None,
                           error=str(e))
