from sqlalchemy.exc import IntegrityError
from app.backend.database.settings import db_session
from app.settings import settings, logger
from app.backend.database.crud.user import put_user, search_users
from app.schemas.user import User, FilterUser

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