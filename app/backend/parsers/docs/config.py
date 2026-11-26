from aiolimiter import AsyncLimiter
from app.backend.ai.functions.rosseti_protocol_extractor import rosseti_get_model_extraction
from app.backend.ai.functions.oem_protocol_extractor import oem_get_model_extraction
from app.backend.ai.functions.itm_protocol_extractor import itm_get_model_extraction
from tenacity import wait_exponential
from kreuzberg import (
    ExtractionConfig,
    OcrConfig,
    PageConfig,
    TesseractConfig
)
from typing import Optional
import asyncio
import httpx
import shutil


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

SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx", ".odt", ".ods",
                        ".doc", ".ott", ".odp", ".rtf"}
ARCHIVE_EXTENSIONS = {".zip", ".rar"}
OFFICE_ZIP_EXTENSIONS = {".docx", ".xlsx", ".pptx", ".odt", ".ods"}

LEGACY_OFFICE_EXTENSIONS = {".doc", ".xls", ".ppt", ".odt", ".ott", ".odp", ".ods"}
LEGACY_TARGET_FORMAT = {
    ".doc": "docx", ".odt": "docx", ".ott": "docx",
    ".xls": "xlsx", ".ods": "xlsx",
    ".ppt": "pptx", ".odp": "pptx",
}

SOFFICE_BIN = shutil.which("soffice") or shutil.which("libreoffice")
SOFFICE_TIMEOUT = 120          # сек на один пакетный вызов
MAX_SOFFICE_BATCH = 50         # файлов за один вызов
SOFFICE_USER_PROFILE = "file:///tmp/lo_profile"  # изоляция профиля

MAX_ARCHIVE_MEMBERS = 500
MAX_ARCHIVE_TOTAL_BYTES = 500 * 1024 * 1024
MAX_ARCHIVE_DEPTH = 5

BLOCKED_TYPES = {
    "application/x-dosexec",
    "application/x-executable",
    "application/x-sharedlib",
    "application/x-msdownload",
}

MIME_TO_EXTENSION = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "application/zip": ".zip",
    "application/vnd.rar": ".rar",
    "application/x-rar-compressed": ".rar",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/rtf": ".rtf",
    "text/rtf": ".rtf",
    "application/msword": ".doc",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.ms-powerpoint": ".ppt",
}

EXT_TO_MIME = {ext: mime for mime, ext in MIME_TO_EXTENSION.items()}

SKIPPED_EXTENSIONS = {
    ".xml",
    ".html",
    ".htm",
}

SKIPPED_MIME_TO_EXTENSION = {
    "text/xml": ".xml",
    "application/xml": ".xml",
    "text/html": ".html",
    "application/xhtml+xml": ".html",
}

PDF_PAGES_CONFIG = ExtractionConfig(pages=PageConfig(extract_pages=True))
OCR_CONFIG = ExtractionConfig(
    force_ocr=True,
    ocr=OcrConfig(
        backend="tesseract",
        language=PDF_TITLE_PAGE_IMAGE_TEXT_LANG,
        tesseract_config=TesseractConfig(psm=6),
    ),
)

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

TASK_PROTOCOL = "protocol"      # уходит в модель — нужен весь документ
TASK_TZ_MARKERS = "tz_markers"  # поиск слов-маячков — нужен весь документ
TASK_DESIGNER = "designer"      # проектировщик с титульника — хватит первой страницы
TASK_NONE = "none"

PROTOCOL_EXTRACTORS = {
    1: rosseti_get_model_extraction,
    2: oem_get_model_extraction,
    3: itm_get_model_extraction,
}

ODF_MIMETYPES = {
    b"application/vnd.oasis.opendocument.text": ".odt",
    b"application/vnd.oasis.opendocument.spreadsheet": ".ods",
    b"application/vnd.oasis.opendocument.presentation": ".odp",
}

filestore_limiter = AsyncLimiter(max_rate=1, time_period=2.5)

download_semaphore = asyncio.Semaphore(DOWNLOAD_CONCURRENCY)
extract_semaphore = asyncio.Semaphore(EXTRACT_CONCURRENCY)
llm_semaphore = asyncio.Semaphore(LLM_CONCURRENCY)

fallback_wait = wait_exponential(multiplier=2, min=5, max=120)

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
