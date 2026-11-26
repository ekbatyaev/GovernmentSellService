from sqlalchemy.exc import IntegrityError
from app.backend.database.settings import db_session
from app.settings import logger
from app.backend.database.crud.user import put_user, search_users
from app.schemas.user import User, FilterUser
from collections import OrderedDict


def merge_unique_list(old: list, new: list) -> list:
    """Объединение списков с дедупом, порядок старых элементов сохраняется."""
    seen = set(old)
    return list(old) + [x for x in new if x not in seen]


def merge_result_info(old: dict, new: dict) -> dict:
    """Union значений полей: дедуп по ';'-чанкам, порядок сохраняется.
    Повторный прогон пайплайна не плодит дубли."""
    result = {}
    for field in set(old) | set(new):
        chunks: "OrderedDict[str, None]" = OrderedDict()
        for source in (old.get(field), new.get(field)):
            for chunk in str(source or "").split(";"):
                chunk = chunk.strip()
                if chunk:
                    chunks[chunk] = None
        result[field] = "; ".join(chunks.keys())
    return result


async def create_admin_user(user: User) -> None:
    async with db_session() as db:
        try:
            users = await search_users(db, FilterUser(email=str(user.email)))
        except IntegrityError as e:
            logger.exception(f"Пользователь админ не создан, произошла ошибка: {e}")
            raise
        if len(users) == 0:
            try:
                await put_user(db, user)
            except IntegrityError as e:
                logger.exception(f"Пользователь админ не создан, произошла ошибка: {e}")
                raise
