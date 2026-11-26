from pathlib import Path
from app.backend.parsers.docs.config import MAX_ARCHIVE_TOTAL_BYTES, BLOCKED_TYPES, MAX_ARCHIVE_MEMBERS
from app.backend.parsers.docs.functions import format_log_kv
from app.backend.parsers.docs.operations.extractors.functions import (sniff_mime, safe_member_target,
                                                                      detect_true_extension)
from app.settings import logger
import asyncio
import zipfile
import rarfile
import time
import stat
import shutil


def _fix_zip_name(name: str) -> str:
    """
    Имена в cp866/cp1251 zipfile прочитал как cp437 — возвращаем кириллицу.
    UTF-8-имена zipfile декодирует сам, их не трогаем.
    """
    if not any(ord(c) > 127 for c in name):
        return name
    best, best_score = name, sum("а" <= c <= "я" or c == "ё" for c in name.lower())
    for enc in ("cp866", "cp1251"):
        try:
            fixed = name.encode("cp437").decode(enc)
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        score = sum("а" <= c <= "я" or c == "ё" for c in fixed.lower())
        if score > best_score:
            best, best_score = fixed, score
    return best


def _extract_zip(path: Path, extract_to: Path) -> int:
    problems: list[str] = []
    extracted = 0

    with zipfile.ZipFile(path, "r") as zf:
        infos = zf.infolist()

        # Проверяем ограничения архива
        if len(infos) > MAX_ARCHIVE_MEMBERS:
            raise ValueError(
                f"Слишком много файлов в архиве: {len(infos)}"
            )

        total = sum(i.file_size for i in infos)

        if total > MAX_ARCHIVE_TOTAL_BYTES:
            raise ValueError(
                f"Архив слишком большой после распаковки: "
                f"{total} байт"
            )

        for info in infos:
            # UTF-8 имена не пытаемся перекодировать
            fixed_name = (
                info.filename
                if info.flag_bits & 0x800
                else _fix_zip_name(info.filename)
            )

            if fixed_name != info.filename:
                logger.info(
                    "ZIP NAME FIXED | %s",
                    format_log_kv(
                        path=path.name,
                        before=info.filename,
                        after=fixed_name,
                    ),
                )

            target = None
            created = False

            try:
                mode = (info.external_attr >> 16) & 0xFFFF

                # Не извлекаем символические ссылки
                if stat.S_ISLNK(mode):
                    logger.warning(
                        "ZIP SKIP MEMBER | %s",
                        format_log_kv(
                            path=path.name,
                            member=fixed_name,
                            reason="symlink",
                        ),
                    )
                    continue

                # Формируем безопасный путь.
                # Длинные имена сокращаются внутри функции.
                try:
                    target = safe_member_target(
                        extract_to, fixed_name
                    )
                except (ValueError, OSError) as e:
                    problems.append(
                        f"Некорректный путь {fixed_name}: {e}"
                    )

                    logger.warning(
                        "ZIP SKIP MEMBER | %s",
                        format_log_kv(
                            path=path.name,
                            member=fixed_name,
                            reason="invalid_path",
                            error=str(e),
                        ),
                    )
                    continue

                # Директории создаём, но не считаем файлами
                if (
                    info.is_dir()
                    or stat.S_ISDIR(mode)
                    or bool(info.external_attr & 0x10)
                ):
                    target.mkdir(
                        parents=True,
                        exist_ok=True,
                    )
                    continue

                # Не перезаписываем существующие файлы
                if target.exists():
                    problems.append(
                        f"Конфликт пути: {fixed_name}"
                    )

                    logger.warning(
                        "ZIP PATH CONFLICT | %s",
                        format_log_kv(
                            path=path.name,
                            member=fixed_name,
                        ),
                    )
                    continue

                # Создаём родительские директории
                target.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                # Распаковываем файл
                with zf.open(info) as src:
                    with target.open("xb") as dst:
                        created = True
                        shutil.copyfileobj(src, dst)

                # Проверяем фактический MIME
                mime = sniff_mime(target)

                if mime in BLOCKED_TYPES:
                    target.unlink(missing_ok=True)
                    created = False

                    logger.warning(
                        "ZIP BLOCKED MEMBER | %s",
                        format_log_kv(
                            path=path.name,
                            member=fixed_name,
                            mime=mime,
                        ),
                    )
                    continue

                extracted += 1

            except Exception as e:
                # Удаляем только созданный нами неполный файл
                if created and target is not None:
                    try:
                        target.unlink(missing_ok=True)
                    except OSError as cleanup_error:
                        logger.warning(
                            "ZIP CLEANUP ERROR | %s",
                            format_log_kv(
                                path=path.name,
                                member=fixed_name,
                                error=str(cleanup_error),
                            ),
                        )

                problems.append(
                    f"Не распакован {fixed_name}: {e}"
                )

                logger.warning(
                    "ZIP BAD MEMBER | %s",
                    format_log_kv(
                        path=path.name,
                        member=fixed_name,
                        error_type=type(e).__name__,
                        error=str(e),
                    ),
                )

                continue

    if problems:
        logger.info(
            "Список проблемных файлов: %s",
            problems,
        )

    return extracted


def _extract_rar(path: Path, extract_to: Path) -> int:
    """
    Распаковка RAR с изоляцией ошибок на уровне члена: битый/зашифрованный
    файл пропускается, остальные распаковываются. Фатальные проблемы
    архива целиком бросают RuntimeError.
    """
    problems: list[str] = []
    try:
        with rarfile.RarFile(path) as rf:
            if rf.needs_password():
                raise RuntimeError("RAR-архив защищён паролем")
            members = rf.infolist()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise ValueError(f"Слишком много файлов в архиве: {len(members)}")

            extracted = 0
            for member in members:
                try:
                    rf.extract(member, path=extract_to)
                    extracted += 1
                except rarfile.PasswordRequired:
                    problems.append(f"под паролем {member.filename}")
                    logger.warning(
                        "RAR SKIP MEMBER | %s",
                        format_log_kv(path=path.name, member=member.filename,
                                      reason="password"),
                    )
                except Exception as e:
                    problems.append(f"не распакован {member.filename}: {e}")
                    logger.warning(
                        "RAR BAD MEMBER | %s",
                        format_log_kv(path=path.name, member=member.filename,
                                      error=str(e)),
                    )

            if len(problems):
                logger.info(f"Список проблемных файлов:\n{problems}")
            return extracted

    except rarfile.BadRarFile as e:
        raise RuntimeError(f"RAR-архив повреждён или имеет неподдерживаемый формат: {e}")
    except rarfile.NeedFirstVolume:
        raise RuntimeError("Для распаковки многотомного RAR нужен первый том архива")
    except rarfile.PasswordRequired:
        raise RuntimeError("RAR-архив защищён паролем")
    except rarfile.RarCannotExec as e:
        raise RuntimeError(f"Не удалось запустить unrar: {e}")
    except (RuntimeError, ValueError):
        raise
    except Exception as e:
        raise RuntimeError(f"Не удалось распаковать RAR: {e}")


async def extract_archive(path: Path, extract_to: Path, task_id: str | None = None) -> None:
    ext = await asyncio.to_thread(
        detect_true_extension, path
    )
    started = time.perf_counter()
    logger.info("EXTRACT START | %s", format_log_kv(task_id=task_id, path=path.name, ext=ext))

    if ext == ".zip" and not zipfile.is_zipfile(path):
        raise ValueError(f"Это не ZIP-архив: {path.name}")
    if ext == ".rar" and not rarfile.is_rarfile(path):
        raise ValueError(f"Это не RAR-архив: {path.name}")

    worker = _extract_zip if ext == ".zip" else _extract_rar
    files = await asyncio.to_thread(worker, path, extract_to)

    logger.info(
        "EXTRACT DONE | %s",
        format_log_kv(
            task_id=task_id, path=path.name, files=files,
            elapsed=f"{time.perf_counter() - started:.3f}s",
        ),
    )
