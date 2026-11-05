from app.backend.parsers.docs.config import ODF_MIMETYPES, OFFICE_ZIP_EXTENSIONS
from pathlib import Path
from typing import Optional
import re
import os
import hashlib

def ensure_dir(path: str | Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path

def format_log_kv(**kwargs) -> str:
    return " | ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)

def stable_id(value: str, length: int | None = None) -> str:
    stable_id = hashlib.md5(value.encode("utf-8", errors="ignore")).hexdigest()
    if length:
        return stable_id[:length]
    return stable_id

def safe_filename(name: str) -> str:
    name = os.path.basename((name or "").strip().replace("\x00", ""))
    return re.sub(r'[<>:"/\\|?*]+', "_", name) or "downloaded_file"

def guess_extension_from_magic(data: bytes, original_name: str = "") -> Optional[str]:
    name = (original_name or "").lower()

    if data.startswith(b"%PDF"):
        return ".pdf"
    if data.startswith(b"Rar!\x1a\x07\x00") or data.startswith(b"Rar!\x1a\x07\x01\x00"):
        return ".rar"
    if data.startswith(b"PK\x03\x04"):
        head = data[:128]
        for mime, ext in ODF_MIMETYPES.items():
            if mime in head:
                return ext
        for ext in OFFICE_ZIP_EXTENSIONS:
            if name.endswith(ext):
                return ext
        return ".zip"
    return None
