from app.backend.parsers.docs.config import (TASK_PROTOCOL, TASK_TZ_MARKERS, TASK_DESIGNER, TASK_NONE,
                                             PROTOCOL_EXTRACTORS)
import re
from pathlib import Path

FULL_TEXT_TASKS = {TASK_PROTOCOL, TASK_TZ_MARKERS}

TZ_FILENAME_RE = re.compile(
    r"(тз|техзадан[а-яё]{1,2}|техническ[а-яё]{1,2}[_\-\s]+задан[а-яё]{1,2})",
    re.IGNORECASE,
)

def classify_document(filename: str, protocol_mode: bool, filter_type: int) -> str:
    filename = str(filename).strip()

    if protocol_mode and "протокол" in filename.lower() and filter_type in PROTOCOL_EXTRACTORS:
        return TASK_PROTOCOL

    if filter_type == 1 and not protocol_mode and Path(filename).suffix.lower() in (".pdf", ".docx", ".docs", ".odt"):
        return TASK_DESIGNER

    if filter_type == 2 and TZ_FILENAME_RE.search(filename):
        return TASK_TZ_MARKERS

    return TASK_NONE