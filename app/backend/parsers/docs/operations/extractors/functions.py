import subprocess
import tempfile
from pathlib import Path
from app.backend.parsers.docs.config import (BLOCKED_TYPES, MIME_TO_EXTENSION, OFFICE_ZIP_EXTENSIONS,
                                             SOFFICE_BIN, LEGACY_OFFICE_EXTENSIONS,
                                             LEGACY_TARGET_FORMAT, MAX_SOFFICE_BATCH, SOFFICE_TIMEOUT,
                                             SOFFICE_USER_PROFILE, SKIPPED_EXTENSIONS, SKIPPED_MIME_TO_EXTENSION)
from app.backend.parsers.docs.functions import format_log_kv
from pathlib import PurePosixPath
from charset_normalizer import from_bytes
from app.settings import logger
import asyncio
import time
import magic
import shutil
import uuid
import hashlib


def _shorten_filename(name: str, max_bytes: int = 240) -> str:
    """
    Сокращает имя файла до допустимой длины в UTF-8.
    Сохраняет расширение и добавляет хеш для предотвращения коллизий.
    """
    encoded = name.encode("utf-8")

    if len(encoded) <= max_bytes:
        return name

    suffix = Path(name).suffix
    stem = name[:-len(suffix)] if suffix else name

    digest = hashlib.sha256(encoded).hexdigest()[:16]

    ending = f"_{digest}{suffix}"
    budget = max_bytes - len(ending.encode("utf-8"))

    if budget <= 0:
        return digest

    shortened = (
        stem.encode("utf-8")[:budget]
        .decode("utf-8", errors="ignore")
    )

    return shortened + ending


def sniff_mime(path: Path) -> str:
    """Реальный MIME-тип по содержимому, а не по расширению."""
    try:
        return magic.from_file(str(path), mime=True)
    except Exception as e:
        logger.warning("MAGIC FAIL | %s", format_log_kv(path=path.name, error=str(e)))
        return "application/octet-stream"


def safe_member_target(extract_to: Path, name: str) -> Path:
    """
    Безопасное формирование пути для распаковки ZIP/RAR.

    - Защита от Zip Slip.
    - Поддержка Windows-разделителей.
    - Сокращение слишком длинных имён.
    - Проверка выхода за пределы директории распаковки.
    """
    name = name.replace("\\", "/")
    pure = PurePosixPath(name)

    if (
        not pure.parts
        or pure.is_absolute()
        or ".." in pure.parts
        or ":" in pure.parts[0]
        or "\x00" in name
    ):
        raise ValueError(
            f"Небезопасное имя файла в архиве: {name!r}"
        )

    parts = []

    for part in pure.parts:
        shortened = _shorten_filename(part)

        if shortened != part:
            logger.info(
                "ARCHIVE NAME SHORTENED | %s",
                format_log_kv(
                    before=part,
                    after=shortened,
                    before_bytes=len(part.encode("utf-8")),
                    after_bytes=len(shortened.encode("utf-8")),
                ),
            )

        parts.append(shortened)

    root = extract_to.resolve()
    target = (root / Path(*parts)).resolve()

    if target == root or not target.is_relative_to(root):
        raise ValueError(
            f"Выход за пределы директории распаковки: {name!r}"
        )

    return target


def _soffice_convert_batch(files: list[Path], out_dir: Path) -> dict[Path, Path] | None:
    """
    Один вызов soffice на пачку файлов одинакового целевого формата.
    Возвращает {исходный путь: конвертированный путь} для успешных.
    """
    if not files or not SOFFICE_BIN:
        return {}

    by_format: dict[str, list[Path]] = {}
    for f in files:
        by_format.setdefault(LEGACY_TARGET_FORMAT.get(f.suffix.lower(), "docx"), []).append(f)

    converted: dict[Path, Path] = {}
    for target_fmt, batch in by_format.items():
        for chunk_start in range(0, len(batch), MAX_SOFFICE_BATCH):
            chunk = batch[chunk_start:chunk_start + MAX_SOFFICE_BATCH]
            profile = f"{SOFFICE_USER_PROFILE}_{uuid.uuid4().hex[:8]}"
            cmd = [
                SOFFICE_BIN,
                f"-env:UserInstallation={profile}",
                "--headless",
                "--norestore",
                "--nolockcheck",
                "--nodefault",
                "--convert-to", target_fmt,
                "--outdir", str(out_dir.resolve()),
                *[str(f.resolve()) for f in chunk],
            ]
            started = time.perf_counter()
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=SOFFICE_TIMEOUT,
                )
                logger.info(
                    "SOFFICE BATCH | %s",
                    format_log_kv(
                        files=len(chunk), fmt=target_fmt, rc=proc.returncode,
                        elapsed=f"{time.perf_counter() - started:.3f}s",
                    ),
                )
            except subprocess.TimeoutExpired:
                logger.error(
                    "SOFFICE TIMEOUT | %s",
                    format_log_kv(files=len(chunk), fmt=target_fmt),
                )
                continue
            finally:
                shutil.rmtree(profile.replace("file://", ""), ignore_errors=True)

            for f in chunk:
                candidate = out_dir / (f.stem + "." + target_fmt)
                if candidate.exists() and candidate.stat().st_size > 0:
                    converted[f] = candidate
                else:
                    logger.warning(
                        "SOFFICE MISS | %s",
                        format_log_kv(path=f.name, fmt=target_fmt),
                    )
    return converted


async def convert_legacy_batch(
    files: list[Path], task_id: str | None = None
) -> tuple[dict[Path, Path], Path | None]:
    """
    Пакетная конвертация legacy-файлов. Вызывать ОДИН РАЗ на батч файлов
    (из merge_files перед фазой извлечения) — стоимость запуска soffice
    делится на всю пачку. Возвращает (маппинг, tmp_dir); tmp_dir удаляет
    вызывающий код после завершения батча.
    """
    legacy = [f for f in files if f.suffix.lower() in LEGACY_OFFICE_EXTENSIONS]
    if not legacy:
        return {}, None
    if not SOFFICE_BIN:
        logger.warning("SOFFICE NOT FOUND | legacy-файлы пойдут напрямую (риск мусора)")
        return {}, None

    tmp = Path(tempfile.mkdtemp(prefix="lo_convert_"))
    try:
        result = await asyncio.to_thread(_soffice_convert_batch, legacy, tmp)
    except Exception as e:
        logger.exception(
            "SOFFICE BATCH ERROR | %s", format_log_kv(task_id=task_id, error=str(e))
        )
        shutil.rmtree(tmp, ignore_errors=True)
        return {}, None
    return result, tmp


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


def detect_true_extension(path: Path) -> str:
    """
    Расширение по содержимому (python-magic).
    Суффикс и содержимое не совпадают — не проблема: файл обрабатывается
    как тот тип, каким он является на самом деле. Не опознано — суффикс.
    """
    ext = path.suffix.lower()
    mime = sniff_mime(path)

    if mime in BLOCKED_TYPES:
        raise ValueError(f"Исполняемый файл: {path.name} ({mime})")

    if mime in SKIPPED_MIME_TO_EXTENSION:
        return SKIPPED_MIME_TO_EXTENSION[mime]

    if mime.endswith("+xml"):
        return ".xml"

    if ext in SKIPPED_EXTENSIONS:
        return ext

    true_ext = MIME_TO_EXTENSION.get(mime)
    if true_ext is None:
        return ext
    if true_ext == ".zip" and ext in OFFICE_ZIP_EXTENSIONS:
        return ext
    return true_ext
