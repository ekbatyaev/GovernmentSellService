from pathlib import Path
from app.backend.parsers.docs.config import SUPPORTED_EXTENSIONS, extract_semaphore
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
from charset_normalizer import from_bytes
from app.backend.parsers.docs.schemas import ExtractInfo
from app.settings import logger
import asyncio
import zipfile
import rarfile
import time


def is_binary_bytes(data: bytes) -> bool:
    if not data:
        return False
    head = data[:4096]
    if b"\x00" in head:
        return True
    text_like = sum(32 <= b <= 126 or b in b"\r\n\t\f\b" or b >= 128 for b in head)
    return (text_like / max(1, len(head))) < 0.75


def detect_encoding(data: bytes) -> str:
    best = from_bytes(data).best()
    if best and best.encoding:
        return best.encoding

    for enc in ("utf-8", "utf-8-sig", "cp1251", "utf-16", "latin-1"):
        try:
            data.decode(enc)
            return enc
        except Exception:
            pass
    return "utf-8"

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

def _extract_zip(path: Path, extract_to: Path) -> int:
    with zipfile.ZipFile(path, "r") as zf:
        members = zf.namelist()
        zf.extractall(extract_to)
    return len(members)


def _extract_rar(path: Path, extract_to: Path) -> int:
    try:
        with rarfile.RarFile(path) as rf:
            if rf.needs_password():
                raise RuntimeError("RAR-архив защищён паролем")
            members = rf.infolist()
            rf.extractall(path=extract_to)
        return len(members)

    except rarfile.BadRarFile as e:
        raise RuntimeError(f"RAR-архив повреждён или имеет неподдерживаемый формат: {e}")
    except rarfile.NeedFirstVolume:
        raise RuntimeError("Для распаковки многотомного RAR нужен первый том архива")
    except rarfile.PasswordRequired:
        raise RuntimeError("RAR-архив защищён паролем")
    except rarfile.RarCannotExec as e:
        raise RuntimeError(f"Не удалось запустить unrar: {e}")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Не удалось распаковать RAR: {e}")

async def extract_archive(path: Path, extract_to: Path, task_id: str | None = None) -> None:
    ext = path.suffix.lower()
    started = time.perf_counter()
    logger.info("EXTRACT START | %s", format_log_kv(task_id=task_id, path=path.name, ext=ext))

    worker = _extract_zip if ext == ".zip" else _extract_rar
    files = await asyncio.to_thread(worker, path, extract_to)

    logger.info(
        "EXTRACT DONE | %s",
        format_log_kv(
            task_id=task_id, path=path.name, files=files,
            elapsed=f"{time.perf_counter() - started:.3f}s",
        ),
    )

async def _extract_text(path: Path, task_id: str | None = None, full_text: bool = False) -> str:
    """
    Единая точка извлечения текста. Бросает ValueError на неподдерживаемый формат.

    full_text=False у PDF означает «только титульный лист» — это оптимизация ровно
    под поиск проектировщика. Для всего остального (протоколы, ТЗ) нужен full_text=True,
    иначе в модель и в поиск слов-маячков уйдёт одна первая страница.
    """
    ext = path.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Пропущен неподдерживаемый формат: {ext or path.name}")

    async with extract_semaphore:
        if ext == ".txt":
            return await asyncio.to_thread(_read_text_file, path)

        if ext == ".pdf":
            if full_text:
                return await _extract_pdf_full_text(path, task_id)
            return await _extract_pdf_title_text(path, task_id)

        result = await extract_file(path)
        return (result.content or "").strip()

async def extract_one(
    path: Path, task_id: str | None, full_text: bool = False
) -> ExtractInfo:
    """Возвращает (path, text, error). Исключения не пробрасывает."""
    started = time.perf_counter()
    try:
        text = await _extract_text(path, task_id=task_id, full_text=full_text)
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