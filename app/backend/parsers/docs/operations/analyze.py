import asyncio
import tempfile
from pathlib import Path
from typing import List, Tuple, Iterable
from app.settings import logger
from app.backend.parsers.docs.functions import format_log_kv
from app.backend.parsers.docs.schemas import ExtractInfo, AnalyzeStats
from app.backend.parsers.docs.operations.extract import extract_one, extract_archive
from app.backend.parsers.docs.config import (SUPPORTED_EXTENSIONS, ARCHIVE_EXTENSIONS,
                                             OFFICE_ZIP_EXTENSIONS)
from app.backend.parsers.docs.operations.accumulate import merge_extracted_into_accumulator, add_processed_document
from app.backend.parsers.docs.operations.classify import classify_document, FULL_TEXT_TASKS
from app.backend.parsers.docs.operations.compute import compute_fields

def iter_candidate_files(target: Path) -> Iterable[Path]:
    for p in sorted(target.rglob("*")):
        if not p.is_file() or is_temp_or_junk_file(p):
            continue
        if p.suffix.lower() in (SUPPORTED_EXTENSIONS | ARCHIVE_EXTENSIONS):
            yield p

def is_temp_or_junk_file(path: Path) -> bool:
    """Временные файлы офисных пакетов и мусор из архивов."""
    name = path.name
    return (
        name.startswith("~$")          # MS Office: ~$документ.docx
        or name.startswith(".~lock.")  # LibreOffice: .~lock.документ.odt#
        or name.startswith("._")       # macOS AppleDouble из zip
        or "__MACOSX" in path.parts    # служебная папка macOS в архивах
    )

def is_office_zip(path: Path) -> bool:
    return path.suffix.lower() in OFFICE_ZIP_EXTENSIONS

async def analyze_file_and_merge_results(
    path: str | Path,
    accumulator: dict,
    documents_accumulator,
    protocol_mode: bool = False,
    filter_type: int = 0,
    task_id: str | None = None,
) -> AnalyzeStats:
    path = Path(path)
    stats = AnalyzeStats()

    logger.info("READ_PATH START | %s", format_log_kv(task_id=task_id, path=path))

    async def merge_files(files: List[Path]) -> None:
        """Извлекаем параллельно, сливаем последовательно — порядок детерминирован."""
        if not files:
            return

        # Фаза 1: извлечение текста параллельно. Сколько текста читать у PDF,
        # решает тот же классификатор, что потом разбирает поля.
        results: list[ExtractInfo] = await asyncio.gather(*(
            extract_one(
                f,
                task_id,
                full_text=classify_document(f.name, protocol_mode, filter_type) in FULL_TEXT_TASKS,
            )
            for f in files
        ))

        pending: List[Tuple[str, str]] = []
        seen_in_batch = set()

        for result in results:
            stats.total += 1

            if result.error or not result.text:
                stats.failed += 1
                continue

            name = result.file_path.name.strip()
            if name in documents_accumulator or name in seen_in_batch:
                logger.info(
                    "DOCUMENT SKIP | %s",
                    format_log_kv(task_id=task_id, filename=name, reason="already_processed"),
                )
                stats.ok += 1
                continue

            seen_in_batch.add(name)
            pending.append((name, result.text))

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
                stats.failed += 1
                continue

            merge_extracted_into_accumulator(accumulator, extracted)
            add_processed_document(documents_accumulator, name)
            stats.ok += 1

    async def walk(target: Path) -> None:
        if not target.exists():
            stats.failed += 1
            stats.total += 1
            return

        if target.is_dir():
            files = list(iter_candidate_files(target))
            if not files:
                stats.failed += 1
                stats.total += 1
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

        if is_temp_or_junk_file(target):
            logger.info(
                "READ_PATH SKIP | %s",
                format_log_kv(task_id=task_id, path=target.name, reason="temp_file"),
            )
            stats.skipped += 1
            stats.total += 1
            return

        ext = target.suffix.lower()
        try:
            if ext in ARCHIVE_EXTENSIONS and not is_office_zip(target):
                with tempfile.TemporaryDirectory() as tmp:
                    await extract_archive(target, Path(tmp), task_id=task_id)
                    await walk(Path(tmp))
                return

            if ext not in SUPPORTED_EXTENSIONS:
                stats.skipped += 1
                stats.total += 1
                return

            await merge_files([target])

        except Exception:
            stats.failed += 1
            stats.total += 1
            logger.exception("READ_PATH ITEM ERROR | %s", format_log_kv(task_id=task_id, path=target))

    await walk(path)

    logger.info("READ_PATH DONE | %s", format_log_kv(task_id=task_id, path=path, **stats.model_dump()))
    return stats
