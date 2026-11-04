from app.backend.parsers.docs.config import (TASK_PROTOCOL, TASK_TZ_MARKERS, TASK_DESIGNER, TASK_NONE,
                                             PROTOCOL_EXTRACTORS, MAX_TEXT_CHARS, llm_semaphore)
from app.settings import logger
from typing import Optional
from app.backend.parsers.docs.operations.classify import classify_document
from app.backend.parsers.docs.functions import format_log_kv

async def _run_llm(extractor, text: str) -> dict:
    # Страховка по объёму: PDF режется при чтении, но протокол может прийти и
    # толстым docx/xlsx, у которых своего лимита нет.
    if len(text) > MAX_TEXT_CHARS:
        logger.warning("LLM INPUT TRUNCATED | %s", format_log_kv(text_len=len(text), limit=MAX_TEXT_CHARS))
        text = text[:MAX_TEXT_CHARS]

    async with llm_semaphore:
        return await extractor(text)

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