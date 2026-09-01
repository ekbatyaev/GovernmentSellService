import asyncio
import hashlib
import mimetypes
import os
import re
import shutil
import tempfile
import time
import zipfile
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import unquote, urlparse

import aiofiles
import httpx
import rarfile
from charset_normalizer import from_bytes
from kreuzberg import (
    ExtractionConfig,
    OcrConfig,
    PageConfig,
    TesseractConfig,
    extract_bytes,
    extract_file,
    render_pdf_page,
)

from app.backend.ai.functions.itm_protocol_extractor import itm_get_model_extraction
from app.backend.ai.functions.oem_protocol_extractor import oem_get_model_extraction
from app.backend.ai.functions.rosseti_protocol_extractor import rosseti_get_model_extraction
from app.settings import logger

# =========================
# Конфигурация
# =========================

CONNECT_TIMEOUT = 15
READ_TIMEOUT = 90
CHUNK_SIZE = 1024 * 1024

DOWNLOAD_CONCURRENCY = 4      # одновременных скачиваний
EXTRACT_CONCURRENCY = 8       # одновременных извлечений текста
LLM_CONCURRENCY = 4           # одновременных обращений к Yandex Cloud

MAX_TEXT_FILE_BYTES = 10 * 1024 * 1024

# Лимиты полного чтения PDF. Взяты из read_pdf_file_pypdf/pymupdf исходной версии:
# там они были заданы, но сами функции никогда не вызывались.
MAX_PDF_PAGES = 10
MAX_TEXT_CHARS = 300_000

# Титульник PDF: сначала текстовый слой первой страницы, если он короткий — OCR
# только первой страницы (не всего документа).
PDF_TITLE_PAGE_MIN_TEXT_CHARS = 80
PDF_TITLE_PAGE_IMAGE_TEXT_ENABLED = True
PDF_TITLE_PAGE_RENDER_DPI = 180
PDF_TITLE_PAGE_IMAGE_TEXT_LANG = "rus+eng"

SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx", ".doc", ".xlsx", ".xls"}
ARCHIVE_EXTENSIONS = {".zip", ".rar"}
OFFICE_ZIP_EXTENSIONS = {".docx", ".xlsx", ".pptx"}

RAR_PART_RE = re.compile(r"^(?P<base>.+)\.part(?P<part>\d+)\.rar$", re.IGNORECASE)
RAR_OLDSTYLE_MAIN_RE = re.compile(r"^(?P<base>.+)\.rar$", re.IGNORECASE)
RAR_OLDSTYLE_SUBPART_RE = re.compile(r"^(?P<base>.+)\.r(?P<part>\d{2})$", re.IGNORECASE)

TZ_FILENAME_RE = re.compile(
    r"(тз|техзадан[а-яё]{1,2}|техническ[а-яё]{1,2}[_\-\s]+задан[а-яё]{1,2})",
    re.IGNORECASE,
)

if not shutil.which("unrar"):
    raise RuntimeError("Не найден системный инструмент unrar")
rarfile.UNRAR_TOOL = "unrar"

FIELDS = {
    "rosseti": [
        "Победитель",
        "Другие участники",
        "Ячейки",
        "Кол-во ячеек",
        "Типовой проект",
        "Проектировщик",
        "Дата исполнения договора",
        "Филиал/РЭС",
    ],
    "itm": ["Победитель", "ИНН", "Итоговая цена контракта", "Другие участники"],
    "oem": ["Победитель", "Слова маячки в тз", "Итоговая цена контракта"],
}

# filter_type -> набор полей и извлекатель протокола.
FIELD_SETS = {1: FIELDS["rosseti"], 2: FIELDS["oem"], 3: FIELDS["itm"]}
PROTOCOL_EXTRACTORS = {
    1: rosseti_get_model_extraction,
    2: oem_get_model_extraction,
    3: itm_get_model_extraction,
}

# Конфиги kreuzberg создаются один раз.
_PDF_PAGES_CONFIG = ExtractionConfig(pages=PageConfig(extract_pages=True))
_OCR_CONFIG = ExtractionConfig(
    force_ocr=True,
    ocr=OcrConfig(
        backend="tesseract",
        language=PDF_TITLE_PAGE_IMAGE_TEXT_LANG,
        tesseract_config=TesseractConfig(psm=6),
    ),
)

_download_semaphore = asyncio.Semaphore(DOWNLOAD_CONCURRENCY)
_extract_semaphore = asyncio.Semaphore(EXTRACT_CONCURRENCY)
_llm_semaphore = asyncio.Semaphore(LLM_CONCURRENCY)

_client: Optional[httpx.AsyncClient] = None
_client_lock = asyncio.Lock()


async def get_client() -> httpx.AsyncClient:
    """
    Отдельный клиент под zakupki.gov.ru. Специально НЕ переиспользуем общий
    settings.async_client: он ходит в Yandex Cloud, а общие дефолтные заголовки
    между двумя разными апстримами — это утечка заголовков в обе стороны.
    """
    global _client
    if _client is None or _client.is_closed:
        async with _client_lock:
            if _client is None or _client.is_closed:
                _client = httpx.AsyncClient(
                    follow_redirects=True,
                    timeout=httpx.Timeout(
                        connect=CONNECT_TIMEOUT,
                        read=READ_TIMEOUT,
                        write=READ_TIMEOUT,
                        pool=READ_TIMEOUT,
                    ),
                    limits=httpx.Limits(max_connections=32, max_keepalive_connections=32),
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/123.0.0.0 Safari/537.36"
                        ),
                        "Referer": "https://zakupki.gov.ru/",
                        "Accept": "*/*",
                    },
                )
    return _client


async def aclose_client() -> None:
    """Вызвать на shutdown приложения."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


# =========================
# Утилиты
# =========================

def format_log_kv(**kwargs) -> str:
    return " | ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)


def stable_id(value: str) -> str:
    return hashlib.md5(value.encode("utf-8", errors="ignore")).hexdigest()


def short_id(value: str) -> str:
    return stable_id(value)[:8]


def ensure_dir(path: str | Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(name: str) -> str:
    name = os.path.basename((name or "").strip().replace("\x00", ""))
    return re.sub(r'[<>:"/\\|?*]+', "_", name) or "downloaded_file"


def normalize_for_title_check(text: str) -> str:
    text = (text or "").replace(" ", " ").replace("Ё", "Е").replace("ё", "е")
    return re.sub(r"\s+", " ", text).strip().lower()


def is_working_documentation_title_page(text: str) -> bool:
    """Титульный лист рабочей документации. Основной маркер: 'РАБОЧАЯ ДОКУМЕНТАЦИЯ'."""
    normalized = normalize_for_title_check(text)
    return bool(normalized) and bool(re.search(r"рабочая\s+документация", normalized))


def is_rar_part_filename(name: str) -> bool:
    name = (name or "").strip()
    return bool(RAR_PART_RE.match(name) or RAR_OLDSTYLE_SUBPART_RE.match(name))


def get_rar_group_info(filename: str) -> Optional[dict]:
    filename = (filename or "").strip()

    m = RAR_PART_RE.match(filename)
    if m:
        part = int(m.group("part"))
        return {"scheme": "part", "base": m.group("base"), "part_num": part, "is_start": part == 1}

    m = RAR_OLDSTYLE_SUBPART_RE.match(filename)
    if m:
        return {
            "scheme": "oldstyle_subpart",
            "base": m.group("base"),
            "part_num": int(m.group("part")) + 1,
            "is_start": False,
        }

    m = RAR_OLDSTYLE_MAIN_RE.match(filename)
    if m:
        return {"scheme": "oldstyle_main", "base": m.group("base"), "part_num": 0, "is_start": True}

    return None


def is_office_zip(path: Path) -> bool:
    return path.suffix.lower() in OFFICE_ZIP_EXTENSIONS


def guess_extension_from_magic(data: bytes, original_name: str = "") -> Optional[str]:
    name = (original_name or "").lower()

    if data.startswith(b"%PDF"):
        return ".pdf"
    if data.startswith(b"Rar!\x1a\x07\x00") or data.startswith(b"Rar!\x1a\x07\x01\x00"):
        return ".rar"
    if data.startswith(b"PK\x03\x04"):
        for ext in (".docx", ".xlsx", ".pptx"):
            if name.endswith(ext):
                return ext
        return ".zip"
    return None


def is_probably_html(data: bytes) -> bool:
    head = data[:4096].lower()
    return b"<html" in head or b"<!doctype html" in head or b"<body" in head


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


# =========================
# Аккумуляторы
# =========================

def init_result_accumulator(field_mode: int = 1) -> dict:
    return {field: OrderedDict() for field in FIELD_SETS[field_mode]}


def init_documents_accumulator(documents_list_old=None):
    return OrderedDict((str(x).strip(), None) for x in (documents_list_old or []) if str(x).strip())


def merge_extracted_into_accumulator(accumulator: dict, extracted: dict) -> None:
    if not extracted:
        return

    for field, value in extracted.items():
        if value is None:
            continue
        value = str(value).strip()
        if not value:
            continue

        bucket = accumulator.setdefault(field, OrderedDict())
        for chunk in str(value).replace("\n", ";").split(";"):
            chunk = chunk.strip()
            if chunk:
                bucket[chunk] = None


def add_processed_document(documents_accumulator, filename: str) -> None:
    filename = str(filename).strip()
    if filename:
        documents_accumulator[filename] = None


def finalize_result_accumulator(accumulator: dict) -> dict:
    return {field: "; ".join(values.keys()) if values else "" for field, values in accumulator.items()}


def finalize_documents_accumulator(documents_accumulator) -> list:
    return list(documents_accumulator.keys())


# =========================
# Доменная логика: проектировщик и слова-маячки
# =========================

def normalize_designer_name(value: str) -> str:
    value = (value or "").replace(" ", " ").replace("“", "«").replace("”", "»")
    if value.count('"') >= 2:
        value = value.replace('"', "«", 1).replace('"', "»", 1)

    value = value.replace("« ", "«").replace(" »", "»")
    value = re.sub(r"\s+", " ", value).strip()

    value = re.sub(r"\bМ\s*-\s*ЭНЕРГО\b", "М-ЭНЕРГО", value, flags=re.IGNORECASE)
    value = re.sub(r"\bМ\s+ЭНЕРГО\b", "М-ЭНЕРГО", value, flags=re.IGNORECASE)
    value = re.sub(
        r"Общество\s+с\s+Ограниченной\s+Ответственностью",
        "Общество с Ограниченной Ответственностью",
        value,
        flags=re.IGNORECASE,
    )
    return value.strip(" ,.;:-")


_DESIGNER_PATTERNS = [
    r"(Общество\s+с\s+Ограниченной\s+Ответственностью\s*[«\"“]\s*[^»\"”\n]{2,120}\s*[»\"”])",
    r"(Общество\s+с\s+Ограниченной\s+Ответственностью\s+[A-ZА-ЯЁ0-9][A-ZА-ЯЁа-яё0-9\s\-]{2,120})",
    r"(ООО\s*[«\"“]\s*[^»\"”\n]{2,120}\s*[»\"”])",
    r"(ПАО\s*[«\"“]\s*[^»\"”\n]{2,120}\s*[»\"”])",
    r"(АО\s*[«\"“]\s*[^»\"”\n]{2,120}\s*[»\"”])",
]

_DESIGNER_STOP_WORDS = (
    "генеральный директор", "главный инженер", "инн", "кпп", "огрн",
    "e-mail", "email", "лист", "стадия", "раздел", "объект",
)

_DESIGNER_LEGAL_FORM_RE = re.compile(
    r"(ООО|АО|ПАО|Общество\s+с\s+Ограниченной\s+Ответственностью)", re.IGNORECASE
)


def extract_designer_from_title_text(text: str) -> str:
    """Достаёт проектировщика с титульного листа. Если явного кандидата нет — ''."""
    if not text or not text.strip():
        return ""

    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in text.replace(" ", " ").splitlines()
        if line and line.strip()
    ]
    candidates = []

    for source_text in ("\n".join(lines), " ".join(lines)):
        for pattern in _DESIGNER_PATTERNS:
            for match in re.finditer(pattern, source_text, flags=re.IGNORECASE | re.MULTILINE):
                candidates.append(normalize_designer_name(match.group(1)))

    # Правовая форма и название на соседних строках.
    for i, line in enumerate(lines):
        if re.fullmatch(r"Общество\s+с\s+Ограниченной\s+Ответственностью", line, flags=re.IGNORECASE):
            if i + 1 < len(lines) and lines[i + 1]:
                candidates.append(normalize_designer_name(f"{line} {lines[i + 1]}"))

    # ООО/АО/ПАО без кавычек в шапке титульника.
    for line in lines[:8]:
        if re.match(r"^(ООО|АО|ПАО)\b", line, flags=re.IGNORECASE):
            candidates.append(normalize_designer_name(line))

    cleaned, seen = [], set()
    for candidate in candidates:
        candidate = normalize_designer_name(candidate)
        lower = candidate.lower()

        if len(candidate) < 5 or lower in seen:
            continue
        if any(word in lower for word in _DESIGNER_STOP_WORDS):
            continue
        if not _DESIGNER_LEGAL_FORM_RE.search(candidate):
            continue

        cleaned.append(candidate)
        seen.add(lower)

    return max(cleaned, key=len) if cleaned else ""


def check_availability_of_fields_from_text(text: str) -> str:
    """
    Ищет признаки ПЧ/УПП/ШУ и т.п. Корни слов, чтобы покрыть падежи и числа.
    """
    pattern = r"(ПЧ|ЧП|УПП|SCADA|ШУ|преобразоват.*частот|устройств.*плавн.*пуск|шкаф.*управл)"
    return "Есть" if re.search(pattern, text, re.IGNORECASE) else "Нету"


# =========================
# Скачивание
# =========================

def guess_filename(response: httpx.Response, url: str, fallback: str = "downloaded_file") -> str:
    cd = response.headers.get("Content-Disposition", "")
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, flags=re.IGNORECASE)
    if match:
        return safe_filename(unquote(match.group(1)))

    name = Path(unquote(urlparse(str(response.url) or url).path)).name
    if name:
        return safe_filename(name)

    content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    return safe_filename(fallback + (mimetypes.guess_extension(content_type) or ""))


async def download_file(
    url: str,
    download_dir: str | Path,
    filename: Optional[str] = None,
    task_id: str | None = None,
) -> Path:
    download_dir = ensure_dir(download_dir)
    client = await get_client()
    started = time.perf_counter()

    logger.info(
        "DOWNLOAD START | %s",
        format_log_kv(task_id=task_id, url=url, filename=filename, download_dir=download_dir),
    )

    async with _download_semaphore:
        async with client.stream("GET", url) as response:
            response.raise_for_status()

            path = download_dir / safe_filename(filename or guess_filename(response, url))
            content_encoding = (response.headers.get("Content-Encoding") or "").lower()
            expected_size = (
                response.headers.get("Content-Length")
                if content_encoding in ("", "identity")
                else None
            )
            written = 0

            async with aiofiles.open(path, "wb") as f:
                async for chunk in response.aiter_bytes(CHUNK_SIZE):
                    if chunk:
                        await f.write(chunk)
                        written += len(chunk)

    if expected_size:
        try:
            if written != int(expected_size):
                raise RuntimeError(f"Файл скачан не полностью: expected={expected_size}, got={written}")
        except ValueError:
            pass

    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError("Файл не скачан или пустой")

    async with aiofiles.open(path, "rb") as f:
        head = await f.read(512)

    if is_probably_html(head):
        raise RuntimeError("Сервер вернул HTML вместо документа")

    magic_ext = guess_extension_from_magic(head[:16], path.name)
    if magic_ext and path.suffix.lower() != magic_ext and not is_rar_part_filename(path.name):
        fixed = path.with_suffix(magic_ext)
        path.rename(fixed)
        path = fixed

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


# =========================
# Извлечение текста (kreuzberg)
# =========================

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
        result = await extract_bytes(png, "image/png", config=_OCR_CONFIG)
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
    result = await extract_file(path, config=_PDF_PAGES_CONFIG)
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
    result = await extract_file(path, config=_PDF_PAGES_CONFIG)
    pages = getattr(result, "pages", None) or []

    if not pages:
        return (result.content or "").strip()[:MAX_TEXT_CHARS]

    parts: List[str] = []
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


async def extract_text(path: Path, task_id: str | None = None, full_text: bool = False) -> str:
    """
    Единая точка извлечения текста. Бросает ValueError на неподдерживаемый формат.

    full_text=False у PDF означает «только титульный лист» — это оптимизация ровно
    под поиск проектировщика. Для всего остального (протоколы, ТЗ) нужен full_text=True,
    иначе в модель и в поиск слов-маячков уйдёт одна первая страница.
    """
    ext = path.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Пропущен неподдерживаемый формат: {ext or path.name}")

    async with _extract_semaphore:
        if ext == ".txt":
            return await asyncio.to_thread(_read_text_file, path)

        if ext == ".pdf":
            if full_text:
                return await _extract_pdf_full_text(path, task_id)
            return await _extract_pdf_title_text(path, task_id)

        result = await extract_file(path)
        return (result.content or "").strip()


# =========================
# Архивы
# =========================

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


def iter_candidate_files(target: Path) -> Iterable[Path]:
    for p in sorted(target.rglob("*")):
        if p.is_file() and p.suffix.lower() in (SUPPORTED_EXTENSIONS | ARCHIVE_EXTENSIONS):
            yield p


# =========================
# Слияние результатов
# =========================

# Что делаем с документом. Один классификатор на два потребителя: он решает и
# сколько текста читать, и как этот текст потом разбирать. Держать их вместе
# важно — иначе легко получить ситуацию, когда прочитали титульник, а разбираем
# как протокол (ровно это и было в исходной версии).
TASK_PROTOCOL = "protocol"      # уходит в модель — нужен весь документ
TASK_TZ_MARKERS = "tz_markers"  # поиск слов-маячков — нужен весь документ
TASK_DESIGNER = "designer"      # проектировщик с титульника — хватит первой страницы
TASK_NONE = "none"

FULL_TEXT_TASKS = {TASK_PROTOCOL, TASK_TZ_MARKERS}


def classify_document(filename: str, protocol_mode: bool, filter_type: int) -> str:
    filename = str(filename).strip()

    if protocol_mode and "протокол" in filename.lower() and filter_type in PROTOCOL_EXTRACTORS:
        return TASK_PROTOCOL

    if filter_type == 1 and not protocol_mode and Path(filename).suffix.lower() in (".pdf", ".docx", ".doc"):
        return TASK_DESIGNER

    if filter_type == 2 and TZ_FILENAME_RE.search(filename):
        return TASK_TZ_MARKERS

    return TASK_NONE


async def _run_llm(extractor, text: str) -> dict:
    # Страховка по объёму: PDF режется при чтении, но протокол может прийти и
    # толстым docx/xlsx, у которых своего лимита нет.
    if len(text) > MAX_TEXT_CHARS:
        logger.warning("LLM INPUT TRUNCATED | %s", format_log_kv(text_len=len(text), limit=MAX_TEXT_CHARS))
        text = text[:MAX_TEXT_CHARS]

    async with _llm_semaphore:
        return await extractor(text)


async def process_text_into_accumulator(
    text: str,
    accumulator: dict,
    documents_accumulator,
    filename: str,
    protocol_mode: bool = False,
    filter_type: int = 0,
    task_id: str | None = None,
) -> bool:
    if not text or not text.strip():
        return False

    filename = str(filename).strip()

    if filename in documents_accumulator:
        logger.info(
            "DOCUMENT SKIP | %s",
            format_log_kv(task_id=task_id, filename=filename, reason="already_processed"),
        )
        return True

    extracted = await compute_fields(text, filename, protocol_mode, filter_type, task_id)
    if extracted is None:
        return False

    merge_extracted_into_accumulator(accumulator, extracted)
    add_processed_document(documents_accumulator, filename)
    return True


async def compute_fields(
    text: str,
    filename: str,
    protocol_mode: bool,
    filter_type: int,
    task_id: str | None = None,
) -> Optional[dict]:
    """
    Считает поля для одного документа. Ничего не мутирует, поэтому безопасно
    вызывать параллельно. None — ошибка, {} — сливать нечего.
    """
    try:
        task = classify_document(filename, protocol_mode, filter_type)

        if task == TASK_PROTOCOL:
            return await _run_llm(PROTOCOL_EXTRACTORS[filter_type], text) or {}

        if task == TASK_DESIGNER and is_working_documentation_title_page(text):
            designer = extract_designer_from_title_text(text)
            if designer:
                logger.info(
                    "PDF DESIGNER EXTRACTED | %s",
                    format_log_kv(task_id=task_id, filename=filename, designer=designer),
                )
                return {"Проектировщик": designer}

            logger.info(
                "PDF DESIGNER NOT FOUND | %s",
                format_log_kv(task_id=task_id, filename=filename, text_len=len(text)),
            )
            return {}

        if task == TASK_TZ_MARKERS:
            found = check_availability_of_fields_from_text(text)
            logger.info(
                "PURCHASE WORK FILE COMPLETED | %s",
                format_log_kv(task_id=task_id, filename=filename, found=found),
            )
            return {"Слова маячки в тз": found}

        return {}

    except Exception as e:
        logger.exception(
            "EXTRACT_FIELDS ERROR | %s",
            format_log_kv(task_id=task_id, filename=filename, error=str(e)),
        )
        return None


async def _extract_one(
    path: Path, task_id: str | None, full_text: bool = False
) -> Tuple[Path, Optional[str], Optional[str]]:
    """Возвращает (path, text, error). Исключения не пробрасывает."""
    started = time.perf_counter()
    try:
        text = await extract_text(path, task_id=task_id, full_text=full_text)
        elapsed = time.perf_counter() - started

        if not text.strip():
            logger.warning(
                "READ_FILE EMPTY | %s",
                format_log_kv(task_id=task_id, filename=path.name, elapsed=f"{elapsed:.3f}s"),
            )
            return path, None, "Текст не извлечен"

        logger.info(
            "READ_FILE DONE | %s",
            format_log_kv(
                task_id=task_id, filename=path.name, ext=path.suffix.lower(),
                text_len=len(text), elapsed=f"{elapsed:.3f}s",
            ),
        )
        return path, text, None

    except ValueError as e:
        logger.warning(
            "READ_FILE NO_TEXT | %s",
            format_log_kv(task_id=task_id, filename=path.name, error=str(e)),
        )
        return path, None, str(e)

    except Exception as e:
        logger.exception(
            "READ_FILE ERROR | %s",
            format_log_kv(task_id=task_id, filename=path.name, error=str(e)),
        )
        return path, None, str(e)


async def read_path_and_merge(
    path: str | Path,
    accumulator: dict,
    documents_accumulator,
    protocol_mode: bool = False,
    filter_type: int = 0,
    task_id: str | None = None,
) -> Dict:
    path = Path(path)
    stats = {"ok": 0, "failed": 0, "skipped": 0, "total": 0}

    logger.info("READ_PATH START | %s", format_log_kv(task_id=task_id, path=path))

    async def merge_files(files: List[Path]) -> None:
        """Извлекаем параллельно, сливаем последовательно — порядок детерминирован."""
        if not files:
            return

        # Фаза 1: извлечение текста параллельно. Сколько текста читать у PDF,
        # решает тот же классификатор, что потом разбирает поля.
        results = await asyncio.gather(*(
            _extract_one(
                f,
                task_id,
                full_text=classify_document(f.name, protocol_mode, filter_type) in FULL_TEXT_TASKS,
            )
            for f in files
        ))

        pending: List[Tuple[str, str]] = []
        seen_in_batch = set()

        for file_path, text, error in results:
            stats["total"] += 1

            if error or not text:
                stats["failed"] += 1
                continue

            name = file_path.name.strip()
            if name in documents_accumulator or name in seen_in_batch:
                logger.info(
                    "DOCUMENT SKIP | %s",
                    format_log_kv(task_id=task_id, filename=name, reason="already_processed"),
                )
                stats["ok"] += 1
                continue

            seen_in_batch.add(name)
            pending.append((name, text))

        if not pending:
            return

        # Фаза 2: расчёт полей параллельно (обращения к модели под семафором).
        computed = await asyncio.gather(*(
            compute_fields(text, name, protocol_mode, filter_type, task_id)
            for name, text in pending
        ))

        # Фаза 3: слияние строго по порядку файлов — результат воспроизводим.
        for (name, _), extracted in zip(pending, computed):
            if extracted is None:
                stats["failed"] += 1
                continue

            merge_extracted_into_accumulator(accumulator, extracted)
            add_processed_document(documents_accumulator, name)
            stats["ok"] += 1

    async def walk(target: Path) -> None:
        if not target.exists():
            stats["failed"] += 1
            stats["total"] += 1
            return

        if target.is_dir():
            files = list(iter_candidate_files(target))
            if not files:
                stats["failed"] += 1
                stats["total"] += 1
                return

            regular = [f for f in files if f.suffix.lower() not in ARCHIVE_EXTENSIONS or is_office_zip(f)]
            archives = [f for f in files if f.suffix.lower() in ARCHIVE_EXTENSIONS and not is_office_zip(f)]

            logger.info(
                "READ_DIR SPLIT | %s",
                format_log_kv(
                    task_id=task_id, path=target,
                    regular_files=len(regular), archive_files=len(archives),
                ),
            )

            await merge_files(regular)
            for archive in archives:
                await walk(archive)
            return

        ext = target.suffix.lower()
        try:
            if ext in ARCHIVE_EXTENSIONS and not is_office_zip(target):
                with tempfile.TemporaryDirectory() as tmp:
                    await extract_archive(target, Path(tmp), task_id=task_id)
                    await walk(Path(tmp))
                return

            if ext not in SUPPORTED_EXTENSIONS:
                stats["skipped"] += 1
                stats["total"] += 1
                return

            await merge_files([target])

        except Exception:
            stats["failed"] += 1
            stats["total"] += 1
            logger.exception("READ_PATH ITEM ERROR | %s", format_log_kv(task_id=task_id, path=target))

    await walk(path)

    logger.info("READ_PATH DONE | %s", format_log_kv(task_id=task_id, path=path, **stats))
    return stats


# =========================
# Многотомные RAR
# =========================

def group_attached_files(attached_files: list) -> list:
    single = []
    part_groups: Dict[str, list] = {}
    oldstyle_main: Dict[str, dict] = {}
    oldstyle_subparts: Dict[str, list] = {}

    for doc in attached_files:
        info = get_rar_group_info((doc.get("filename") or "").strip())

        if not info:
            single.append({"group_type": "single", "doc": doc})
            continue

        entry = {
            "doc": doc,
            "part_num": info["part_num"],
            "is_start": info["is_start"],
            "base": info["base"],
        }

        if info["scheme"] == "part":
            part_groups.setdefault(info["base"], []).append(entry)
        elif info["scheme"] == "oldstyle_main":
            oldstyle_main[info["base"]] = entry
        elif info["scheme"] == "oldstyle_subpart":
            oldstyle_subparts.setdefault(info["base"], []).append(entry)

    result = single[:]

    for base, parts in part_groups.items():
        parts.sort(key=lambda x: x["part_num"])
        result.append({"group_type": "multipart_rar", "base": base, "scheme": "part", "parts": parts})

    for base, subparts in oldstyle_subparts.items():
        parts = ([oldstyle_main[base]] if base in oldstyle_main else []) + subparts
        parts.sort(key=lambda x: x["part_num"])
        result.append({"group_type": "multipart_rar", "base": base, "scheme": "oldstyle", "parts": parts})

    # Одиночные .rar без сопутствующих томов.
    for base, entry in oldstyle_main.items():
        if base not in oldstyle_subparts:
            result.append({"group_type": "single", "doc": entry["doc"]})

    return result


async def download_multipart_rar(parts: list, work_dir: Path, task_id: str | None = None) -> Path:
    logger.info("MULTIPART_RAR START | %s", format_log_kv(task_id=task_id, parts=len(parts)))

    paths = await asyncio.gather(*(
        download_file(
            url=item["doc"]["url"],
            download_dir=work_dir,
            filename=item["doc"].get("filename"),
            task_id=task_id,
        )
        for item in parts
    ))

    downloaded = sorted(
        ({"path": p, "part_num": item["part_num"], "is_start": item["is_start"]}
         for p, item in zip(paths, parts)),
        key=lambda x: x["part_num"],
    )

    start_parts = [x for x in downloaded if x["is_start"]]
    chosen = (start_parts[0] if start_parts else downloaded[0])["path"]

    logger.info(
        "MULTIPART_RAR DONE | %s",
        format_log_kv(task_id=task_id, chosen=chosen.name, total_parts=len(downloaded)),
    )
    return chosen


# =========================
# Интеграция
# =========================

async def process_one_attached_file_and_merge(
    item: dict,
    tmp_dir: Path,
    accumulator: dict,
    documents_accumulator,
    protocol_mode: bool = False,
    filter_type: int = 1,
) -> dict:
    work_dir = None
    started = time.perf_counter()

    try:
        group_type = item["group_type"]

        if group_type == "single":
            doc = item["doc"]
            source_url = doc["url"]
            source_name = doc.get("filename") or "file"
            task_id = short_id(source_url)

            work_dir = ensure_dir(tmp_dir / f"{safe_filename(source_name)}_{stable_id(source_url)}")
            logger.info(
                "ATTACHED START | %s",
                format_log_kv(task_id=task_id, group_type=group_type, source_name=source_name),
            )

            target = await download_file(
                url=source_url,
                download_dir=work_dir,
                filename=doc.get("filename"),
                task_id=task_id,
            )

        elif group_type == "multipart_rar":
            base = item["base"]
            parts = item["parts"]
            source_url = " | ".join(p["doc"]["url"] for p in parts)
            task_id = short_id(source_url)

            work_dir = ensure_dir(tmp_dir / f"{safe_filename(base)}_{stable_id(source_url)}")
            logger.info(
                "ATTACHED START | %s",
                format_log_kv(task_id=task_id, group_type=group_type, base=base, parts=len(parts)),
            )

            target = await download_multipart_rar(parts, work_dir, task_id=task_id)

        else:
            raise RuntimeError(f"Неизвестный group_type: {group_type}")

        stats = await read_path_and_merge(
            target, accumulator, documents_accumulator, protocol_mode, filter_type, task_id=task_id
        )

        logger.info(
            "ATTACHED DONE | %s",
            format_log_kv(
                task_id=task_id, group_type=group_type,
                elapsed=f"{time.perf_counter() - started:.3f}s", **stats,
            ),
        )
        return {"source_url": source_url, "error": None, "stats": stats}

    except httpx.HTTPError as e:
        logger.exception("ATTACHED DOWNLOAD ERROR")
        return {"source_url": item, "error": f"Ошибка скачивания: {e}", "stats": None}

    except Exception as e:
        logger.exception("ATTACHED PROCESS ERROR")
        return {"source_url": item, "error": f"Ошибка обработки: {e}", "stats": None}

    finally:
        if work_dir and work_dir.exists():
            await asyncio.to_thread(shutil.rmtree, work_dir, ignore_errors=True)


async def process_attached_files_and_merge(
    attached_files: list,
    tmp_dir: str | Path,
    result_info_old,
    documents_list_old,
    protocol_mode: bool = False,
    filter_type: int = 1,
) -> Tuple[Dict, List]:
    """
    Основная точка входа (async). Синхронный вариант — process_attached_files_and_merge_sync.
    """
    tmp_dir = ensure_dir(tmp_dir)
    accumulator = init_result_accumulator(field_mode=filter_type)
    merge_extracted_into_accumulator(accumulator, result_info_old)
    documents_accumulator = init_documents_accumulator(documents_list_old)

    if not attached_files:
        logger.info("ATTACHED BATCH SKIP | reason=no_attached_files")
        return (
            finalize_result_accumulator(accumulator),
            finalize_documents_accumulator(documents_accumulator),
        )

    grouped_items = group_attached_files(attached_files)
    logger.info("ATTACHED BATCH START | %s", format_log_kv(groups=len(grouped_items), tmp_dir=tmp_dir))
    batch_started = time.perf_counter()

    # Группы верхнего уровня — последовательно: порядок слияния в аккумулятор
    # влияет на итоговый выбор Проектировщика, он должен быть воспроизводимым.
    for idx, item in enumerate(grouped_items, start=1):
        item_started = time.perf_counter()
        await process_one_attached_file_and_merge(
            item, tmp_dir, accumulator, documents_accumulator, protocol_mode, filter_type
        )
        logger.info(
            "ATTACHED BATCH ITEM DONE | %s",
            format_log_kv(
                index=idx, total=len(grouped_items), group_type=item.get("group_type"),
                elapsed=f"{time.perf_counter() - item_started:.3f}s",
            ),
        )

    logger.info(
        "ATTACHED BATCH DONE | %s",
        format_log_kv(groups=len(grouped_items), elapsed=f"{time.perf_counter() - batch_started:.3f}s"),
    )

    result = finalize_result_accumulator(accumulator)

    if filter_type == 1:
        result["Проектировщик"] = pick_longest_designer(result.get("Проектировщик", ""))

    if filter_type == 2:
        result["Слова маячки в тз"] = "Есть" if "Есть" in result.get("Слова маячки в тз", "") else "Нету"

    return result, finalize_documents_accumulator(documents_accumulator)


def process_attached_files_and_merge_sync(*args, **kwargs) -> Tuple[Dict, List]:
    """Тонкая обёртка для синхронных вызывающих. Нельзя вызывать из работающего event loop."""
    return asyncio.run(process_attached_files_and_merge(*args, **kwargs))


def pick_longest_designer(value: str) -> str:
    parts = []
    for x in (value or "").split(";"):
        x = x.strip()
        if x and x not in parts:
            parts.append(x)
    return max(parts, key=len) if parts else ""


if __name__ == "__main__":
    import json

    async def _main():
        folder = Path("/app/app/goszakupki_requests/tmp/ул. Феодосийская, зу 7 (extract.me)")

        accumulator = init_result_accumulator()
        documents_accumulator = init_documents_accumulator([])
        stats = await read_path_and_merge(folder, accumulator, documents_accumulator, task_id="local_test")

        result = finalize_result_accumulator(accumulator)
        result["Проектировщик"] = pick_longest_designer(result.get("Проектировщик", ""))

        print("STATS:", json.dumps(stats, ensure_ascii=False, indent=2))
        print("RESULT:", json.dumps(result, ensure_ascii=False, indent=2))
        await aclose_client()

    asyncio.run(_main())