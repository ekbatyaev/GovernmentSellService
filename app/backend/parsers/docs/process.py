import asyncio
import shutil
import time
import httpx
from pathlib import Path
from typing import Dict, List, Tuple
from app.backend.parsers.docs.operations.analyze import analyze_file_and_merge_results
from app.schemas.purchase import Document
from app.settings import logger
from app.backend.parsers.docs.functions import ensure_dir, format_log_kv, stable_id, safe_filename
from app.backend.parsers.docs.operations.accumulate import (init_result_accumulator,
                                                            merge_extracted_into_accumulator,
                                                            init_documents_accumulator,
                                                            finalize_result_accumulator,
                                                            finalize_documents_accumulator)
from app.backend.parsers.docs.schemas import GroupFileAnalysis, Entry, AnalyzeStats, ProcessStats
from app.backend.parsers.docs.operations.accumulate import accumulate_attached_files
from app.backend.parsers.docs.operations.download import download_file, download_multipart_rar
from app.backend.parsers.docs.operations.regex.fields import pick_longest_designer

async def process_one_attached_file_and_merge(
    item: GroupFileAnalysis,
    tmp_dir: Path,
    accumulator: dict,
    documents_accumulator,
    protocol_mode: bool = False,
    filter_type: int = 1,
) -> ProcessStats:

    result: ProcessStats
    work_dir = None
    started = time.perf_counter()

    try:

        if item.group_type == "single":
            doc: Document = item.parts[0].doc
            source_url = doc.url
            source_name = doc.filename
            task_id = stable_id(source_url, 8)

            work_dir = ensure_dir(tmp_dir / f"{safe_filename(source_name)}_{stable_id(source_url)}")
            logger.info(
                "ATTACHED START | %s",
                format_log_kv(task_id=task_id, group_type=item.group_type, source_name=source_name),
            )

            target = await download_file(
                url=source_url,
                download_dir=work_dir,
                filename=doc.filename,
                task_id=task_id
            )

        elif item.group_type == "multipart_rar":
            base = item.base
            parts: list[Entry] = item.parts
            source_url = " | ".join(p.doc.url for p in parts)
            task_id = stable_id(source_url, 8)

            work_dir = ensure_dir(tmp_dir / f"{safe_filename(base)}_{stable_id(source_url)}")
            logger.info(
                "ATTACHED START | %s",
                format_log_kv(task_id=task_id, group_type=item.group_type, base=base, parts=len(parts)),
            )

            target = await download_multipart_rar(parts, work_dir, task_id=task_id)

        else:
            raise RuntimeError(f"Неизвестный group_type: {item.group_type}")

        stats: AnalyzeStats = await analyze_file_and_merge_results(
            target, accumulator, documents_accumulator, protocol_mode, filter_type, task_id=task_id
        )

        logger.info(
            "ATTACHED DONE | %s",
            format_log_kv(
                task_id=task_id, group_type=item.group_type,
                elapsed=f"{time.perf_counter() - started:.3f}s", **stats.model_dump(),
            ),
        )
        result = ProcessStats(source_url=source_url, stats=stats)

    except httpx.HTTPError as e:
        logger.exception("ATTACHED DOWNLOAD ERROR")
        result = ProcessStats(error=f"Ошибка скачивания: {e}", stats=None)

    except Exception as e:
        logger.exception("ATTACHED PROCESS ERROR")
        result = ProcessStats(error=f"Ошибка обработки: {e}", stats=None)

    finally:
        if work_dir and work_dir.exists():
            await asyncio.to_thread(shutil.rmtree, work_dir, ignore_errors=True)

    return result

async def process_attached_files_and_merge(
    attached_files: list,
    tmp_dir: str | Path,
    result_info_old,
    documents_list_old,
    protocol_mode: bool = False,
    filter_type: int = 1,
) -> Tuple[Dict, List]:
    """
    Основная точка входа (async).
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

    grouped_items: list[GroupFileAnalysis] = accumulate_attached_files(attached_files)
    logger.info("ATTACHED BATCH START | %s", format_log_kv(groups=len(grouped_items), tmp_dir=tmp_dir))
    batch_started = time.perf_counter()

    # Группы верхнего уровня — последовательно: порядок слияния в аккумулятор
    # влияет на итоговый выбор Проектировщика, он должен быть воспроизводимым.
    for idx, item in enumerate(grouped_items, start=1):
        item_started = time.perf_counter()
        process_stats: ProcessStats = await process_one_attached_file_and_merge(
            item, tmp_dir, accumulator, documents_accumulator, protocol_mode, filter_type
        )
        if not process_stats.error:
            logger.info(
                "ATTACHED BATCH ITEM DONE SUCCESSFULLY| %s",
                format_log_kv(
                    index=idx, total=len(grouped_items), group_type=item.group_type,
                    elapsed=f"{time.perf_counter() - item_started:.3f}s",
                ),
            )
        else:
            logger.warning(
                "ATTACHED BATCH ITEM DONE WITH ERROR| %s",
                format_log_kv(
                    index=idx, total=len(grouped_items), group_type=item.group_type,
                    elapsed=f"{time.perf_counter() - item_started:.3f}s",
                ),
            )
            logger.warning(f"ERROR: {process_stats.error}")


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
