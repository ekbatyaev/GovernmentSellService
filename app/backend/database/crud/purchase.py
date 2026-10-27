from sqlalchemy.exc import IntegrityError
from app.schemas.purchase import Notice, FilterNotice, UpdateNotice
from sqlalchemy.ext.asyncio import AsyncSession
from app.backend.database.models import NoticeDatabase
from sqlalchemy import select, or_
from datetime import datetime, timedelta
from typing import Literal

async def put_purchase(db: AsyncSession, notice: Notice) -> NoticeDatabase:
    new_purchase = NoticeDatabase(**notice.model_dump())
    db.add(new_purchase)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise
    await db.refresh(new_purchase)
    return new_purchase

async def search_purchases(db: AsyncSession, filters: FilterNotice) -> list[Notice]:
    query = select(NoticeDatabase)

    if filters.name:
        query = query.where(NoticeDatabase.name.ilike(f"%{filters.name}%"))

    if filters.registration_number:
        query = query.where(NoticeDatabase.registration_number == filters.registration_number)

    if filters.list_filter_type_name:
        query = query.where(NoticeDatabase.filter_type_name.in_(filters.list_filter_type_name))

    types = filters.list_filter_type_name or []

    if "Тендеры для OEM" in types and filters.oem_flag:
        query = query.where(
            or_(
                NoticeDatabase.filter_type_name != "Тендеры для OEM",
                NoticeDatabase.result_info["Слова маячки в тз"].astext == filters.oem_flag,
            )
        )

    if "Тендеры для ITM" in types and filters.itm_option:
        query = query.where(
            or_(
                NoticeDatabase.filter_type_name != "Тендеры для ITM",
                NoticeDatabase.result_info["Категория заявки"].astext == filters.itm_option,
            )
        )

    if filters.region_numbers:
        query = query.where(NoticeDatabase.region_number.in_(filters.region_numbers))

    if filters.initial_sum_from:
        query = query.where(NoticeDatabase.initial_sum >= filters.initial_sum_from)

    if filters.initial_sum_to:
        query = query.where(NoticeDatabase.initial_sum <= filters.initial_sum_to)

    if filters.publication_datetime_from:
        start = datetime.combine(filters.publication_datetime_from.date(), datetime.min.time())
        query = query.where(NoticeDatabase.publication_datetime >= start)

    if filters.publication_datetime_to:
        end = datetime.combine(filters.publication_datetime_to.date(), datetime.min.time()) + timedelta(days=1)
        query = query.where(NoticeDatabase.publication_datetime < end)

    if filters.submission_start_datetime_from:
        start = datetime.combine(filters.submission_start_datetime_from.date(), datetime.min.time())
        query = query.where(NoticeDatabase.submission_start_datetime >= start)

    if filters.submission_start_datetime_to:
        end = datetime.combine(filters.submission_start_datetime_to.date(), datetime.min.time()) + timedelta(days=1)
        query = query.where(NoticeDatabase.submission_start_datetime < end)

    if filters.submission_close_datetime_from:
        start = datetime.combine(filters.submission_close_datetime_from.date(), datetime.min.time())
        query = query.where(NoticeDatabase.submission_close_datetime >= start)
    if filters.submission_close_datetime_to:
        end = datetime.combine(filters.submission_close_datetime_to.date(), datetime.min.time()) + timedelta(days=1)
        query = query.where(NoticeDatabase.submission_close_datetime < end)

    if filters.source_file:
        query = query.where(NoticeDatabase.source_file == filters.source_file)

    query = query.order_by(NoticeDatabase.publication_datetime.desc().nullslast())

    result = await db.execute(query)
    purchases = result.scalars().all()
    data = [Notice.model_validate(p) for p in purchases]
    return data

async def get_purchase(db: AsyncSession, guid: str) -> Notice | None:
    purchase = await db.get(NoticeDatabase, guid)
    return purchase

async def delete_purchase(db: AsyncSession, guid: str) -> bool:
    purchase = await db.get(NoticeDatabase, guid)
    if not purchase:
        return False
    await db.delete(purchase)
    await db.commit()
    return True

async def update_purchase(db: AsyncSession, guid: str, updated_notice: UpdateNotice) -> Literal["not found", "updated"]:
    query = select(NoticeDatabase).where(NoticeDatabase.guid == guid)

    notice = await db.scalar(query)

    if not notice:
        return "not found"

    update_data = updated_notice.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(notice, field, value)

    try:
        await db.commit()
        await db.refresh(notice)
    except IntegrityError:
        await db.rollback()
        raise

    return "updated"