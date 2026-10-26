from datetime import datetime
from app.settings import logger, MOSCOW_TZ
from sqlalchemy.ext.asyncio import AsyncSession
from app.backend.database.crud.purchase import search_purchases, delete_purchase
from app.schemas.purchase import FilterNotice
from sqlalchemy.exc import IntegrityError

def moscow_datetime() -> datetime:
    return datetime.now(MOSCOW_TZ).replace(tzinfo=None)

async def clean_old_notices(db: AsyncSession, delete_date_to: datetime) -> None:
    try:
        purchases = await search_purchases(db, FilterNotice(publication_datetime_to=delete_date_to))
    except IntegrityError as e:
        logger.exception(f"Произошла ошибка получения данных заявок: {e}")
        raise

    deleted_count = 0
    for purchase in purchases:
        try:
            delete_status = await delete_purchase(db, purchase.guid)
            deleted_count += int(delete_status)

        except IntegrityError as e:
            logger.exception(f"Произошла ошибка удаления старой заявки: {e}")
            continue

    logger.info(
        f"Daily job: успешно удалено {deleted_count} заявок из {len(purchases)}"
    )

async def clean_old_auth_codes(db: AsyncSession, delete_date_to: datetime) -> None:
    try:
        purchases = await search_purchases(db, FilterNotice(publication_datetime_to=delete_date_to))
    except IntegrityError as e:
        logger.exception(f"Произошла ошибка получения данных заявок: {e}")
        raise

    deleted_count = 0
    for purchase in purchases:
        try:
            delete_status = await delete_purchase(db, purchase.guid)
            deleted_count += int(delete_status)

        except IntegrityError as e:
            logger.exception(f"Произошла ошибка удаления старой заявки: {e}")
            continue

    logger.info(
        f"Daily job: успешно удалено {deleted_count} заявок из {len(purchases)}"
    )
