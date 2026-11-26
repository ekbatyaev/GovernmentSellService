import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import List, Tuple, Iterable
from app.settings import logger
from app.backend.parsers.docs.functions import format_log_kv
from app.backend.parsers.docs.schemas import ExtractInfo, AnalyzeStats
from app.backend.parsers.docs.operations.extractors.archives import extract_archive
from app.backend.parsers.docs.operations.extractors.files import (extract_one, convert_legacy_batch,
                                                                  detect_true_extension)
from app.backend.parsers.docs.config import (SUPPORTED_EXTENSIONS, ARCHIVE_EXTENSIONS,
                                             OFFICE_ZIP_EXTENSIONS, MAX_ARCHIVE_DEPTH)
from app.backend.parsers.docs.operations.accumulate import merge_extracted_into_accumulator, add_processed_document
from app.backend.parsers.docs.operations.classify import classify_document, FULL_TEXT_TASKS
from app.backend.parsers.docs.operations.compute import compute_fields


def iter_candidate_files(target: Path) -> Iterable[Path]:
    for p in sorted(target.rglob("*")):
        if p.is_file() and not p.is_symlink():
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

        converted_map, lo_tmp = await convert_legacy_batch(files, task_id)
        try:

            results: list[ExtractInfo] = await asyncio.gather(*(
                extract_one(
                    f,
                    task_id,
                    full_text=classify_document(f.name, protocol_mode, filter_type) in FULL_TEXT_TASKS,
                    converted_legacy=converted_map.get(f),
                )
                for f in files
            ))

            pending: List[Tuple[str, str]] = []
            seen_in_batch = set()

            for result in results:
                stats.total += 1

                if result.skipped:
                    stats.skipped += 1
                    continue

                if result.error or not result.text:
                    stats.failed += 1
                    continue

                name = result.path.name.strip()
                if name in documents_accumulator or name in seen_in_batch:
                    logger.info(
                        "DOCUMENT SKIP | %s",
                        format_log_kv(task_id=task_id, filename=name, reason="already_processed"),
                    )
                    stats.skipped += 1
                    continue

                seen_in_batch.add(name)
                pending.append((name, result.text))

            if not pending:
                return

            computed = await asyncio.gather(
                *(
                    compute_fields(
                        text,
                        name,
                        protocol_mode,
                        filter_type,
                        task_id,
                    )
                    for name, text in pending
                ),
                return_exceptions=True,
            )

            for (name, _), extracted in zip(pending, computed):
                if isinstance(extracted, asyncio.CancelledError):
                    raise extracted

                if isinstance(extracted, Exception):
                    stats.failed += 1

                    logger.error(
                        "COMPUTE FIELDS ERROR | %s",
                        format_log_kv(
                            task_id=task_id,
                            filename=name,
                            error_type=type(extracted).__name__,
                            error=str(extracted),
                        ),
                    )
                    continue

                if extracted is None:
                    stats.failed += 1
                    continue

                merge_extracted_into_accumulator(
                    accumulator, extracted
                )

                add_processed_document(
                    documents_accumulator, name
                )

                stats.ok += 1

        finally:
            if lo_tmp:
                shutil.rmtree(lo_tmp, ignore_errors=True)

    async def walk(target: Path, depth: int = 0) -> None:
        try:
            if not target.exists():
                stats.failed += 1
                stats.total += 1

                logger.warning(
                    "READ_PATH NOT FOUND | %s",
                    format_log_kv(
                        task_id=task_id,
                        path=target,
                    ),
                )
                return

            # Обработка директории
            if target.is_dir():
                files = list(iter_candidate_files(target))

                # Пустая директория — не ошибка чтения
                if not files:
                    stats.skipped += 1
                    stats.total += 1

                    logger.info(
                        "READ_DIR EMPTY | %s",
                        format_log_kv(
                            task_id=task_id,
                            path=target,
                        ),
                    )
                    return

                regular: list[Path] = []
                archives: list[Path] = []

                for f in files:
                    if is_temp_or_junk_file(f):
                        stats.skipped += 1
                        stats.total += 1
                        continue

                    try:
                        true_ext = await asyncio.to_thread(
                            detect_true_extension, f
                        )

                    except ValueError as e:
                        stats.skipped += 1
                        stats.total += 1

                        logger.info(
                            "READ_PATH SKIP | %s",
                            format_log_kv(
                                task_id=task_id,
                                path=f.name,
                                reason=str(e),
                            ),
                        )
                        continue

                    except Exception as e:
                        stats.failed += 1
                        stats.total += 1

                        logger.warning(
                            "READ_PATH DETECT ERROR | %s",
                            format_log_kv(
                                task_id=task_id,
                                path=f.name,
                                error=str(e),
                            ),
                        )
                        continue

                    if true_ext in ARCHIVE_EXTENSIONS:
                        archives.append(f)

                    elif true_ext in SUPPORTED_EXTENSIONS:
                        regular.append(f)

                    else:
                        stats.skipped += 1
                        stats.total += 1

                        logger.info(
                            "READ_PATH SKIP | %s",
                            format_log_kv(
                                task_id=task_id,
                                path=f.name,
                                reason="unsupported_format",
                                ext=true_ext,
                            ),
                        )

                logger.info(
                    "READ_DIR SPLIT | %s",
                    format_log_kv(
                        task_id=task_id,
                        path=target,
                        regular_files=len(regular),
                        archive_files=len(archives),
                    ),
                )

                await merge_files(regular)

                for archive in archives:
                    await walk(archive, depth)

                return

            # Пропускаем временные файлы
            if target.is_symlink() or is_temp_or_junk_file(target):
                stats.skipped += 1
                stats.total += 1

                logger.info(
                    "READ_PATH SKIP | %s",
                    format_log_kv(
                        task_id=task_id,
                        path=target.name,
                        reason="temp_or_symlink",
                    ),
                )
                return

            # Определяем настоящий формат
            try:
                true_ext = await asyncio.to_thread(
                    detect_true_extension, target
                )
            except ValueError as e:
                stats.skipped += 1
                stats.total += 1

                logger.info(
                    "READ_PATH SKIP | %s",
                    format_log_kv(
                        task_id=task_id,
                        path=target.name,
                        reason=str(e),
                    ),
                )
                return

            # Обрабатываем архив
            if true_ext in ARCHIVE_EXTENSIONS:
                if depth >= MAX_ARCHIVE_DEPTH:
                    stats.failed += 1
                    stats.total += 1

                    logger.warning(
                        "ARCHIVE DEPTH LIMIT | %s",
                        format_log_kv(
                            task_id=task_id,
                            path=target.name,
                            depth=depth,
                        ),
                    )
                    return

                with tempfile.TemporaryDirectory() as tmp:
                    await extract_archive(
                        target,
                        Path(tmp),
                        task_id=task_id,
                    )

                    await walk(Path(tmp), depth + 1)

                return

            # Неподдерживаемый формат — штатный пропуск
            if true_ext not in SUPPORTED_EXTENSIONS:
                stats.skipped += 1
                stats.total += 1

                logger.info(
                    "READ_PATH SKIP | %s",
                    format_log_kv(
                        task_id=task_id,
                        path=target.name,
                        reason="unsupported_format",
                        ext=true_ext,
                    ),
                )
                return

            # Обычный документ
            await merge_files([target])

        except Exception:
            stats.failed += 1
            stats.total += 1

            logger.exception(
                "READ_PATH ITEM ERROR | %s",
                format_log_kv(
                    task_id=task_id,
                    path=target,
                ),
            )

    await walk(path)

    logger.info("READ_PATH DONE | %s", format_log_kv(task_id=task_id, path=path, **stats.model_dump()))
    return stats
