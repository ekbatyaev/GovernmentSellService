from app.backend.parsers.docs.config import ODF_MIMETYPES, OFFICE_ZIP_EXTENSIONS
from app.settings import settings
from pathlib import Path
from typing import Optional
from pathlib import PurePosixPath
import re
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
    basename = (name or "").strip().replace("\x00", "")
    basename = basename.replace("\\", "/").rsplit("/", 1)[-1]
    basename = re.sub(r'[<>:"|?*]+', "_", basename).rstrip(" .")
    basename = basename or "downloaded_file"

    limit = settings.max_filename_bytes
    encoded = basename.encode("utf-8")
    if len(encoded) <= limit:
        return basename

    suffix = PurePosixPath(basename).suffix
    stem = basename[:-len(suffix)] if suffix else basename
    digest = hashlib.sha256(encoded).hexdigest()[:12]
    tail = f"-{digest}{suffix}"

    stem_budget = limit - len(tail.encode("utf-8"))
    if stem_budget < 1:
        raise ValueError("max_filename_bytes is too small for the file extension")

    prefix = stem.encode("utf-8")[:stem_budget].decode("utf-8", errors="ignore")
    return f"{prefix.rstrip(' ._') or '_'}{tail}"


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
