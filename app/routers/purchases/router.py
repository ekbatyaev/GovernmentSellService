from datetime import datetime, timedelta
from fastapi import HTTPException
from fastapi import APIRouter
from app.routers.dependencies import require_token
from app.routers.schemas import ResponseModel
from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.backend.db.settings import get_db
from app.schemas.purchase import Notice
from app.routers.purchases.schemas import UpdateNotice, FilterNotice
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from app.backend.db.models import NoticeDatabase

purchase_router = APIRouter(prefix = "/purchases", tags=["purchases"], dependencies=[Depends(require_token)])

@purchase_router.post("", response_model = ResponseModel, status_code=status.HTTP_201_CREATED)
async def put_purchase(notice: Notice, db: AsyncSession = Depends(get_db)):

    new_purchase = Notice(**notice.model_dump())

    try:
        db.add(new_purchase)
        await db.commit()
        await db.refresh(new_purchase)
        return ResponseModel(
            status_message="created",
            data=Notice.model_validate(new_purchase)
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Failed to create purchase")

@purchase_router.get("", response_model=ResponseModel, status_code=status.HTTP_302_FOUND)
async def search_purchases(
        filters: FilterNotice,
        db: AsyncSession = Depends(get_db)
    ):
    query = select(NoticeDatabase)

    if filters.name:
        query = query.where(NoticeDatabase.name.ilike(f"%{filters.name}%"))

    if filters.list_filter_type_name:
        query = query.where(NoticeDatabase.filter_type_name.in_(filters.list_filter_type_name))

    if "Тендеры для OEM" in filters.list_filter_type_name and filters.oem_flag:
        query = query.where(
            or_(
                NoticeDatabase.filter_type_name != "Тендеры для OEM",
                NoticeDatabase.result_info["Слова маячки в тз"].astext == filters.oem_flag,
            )
        )

    if "Тендеры для ITM" in filters.list_filter_type_name and filters.itm_option:
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
    return ResponseModel(status_message="found", data=data)

@purchase_router.get("/{guid}", response_model=ResponseModel, status_code=status.HTTP_302_FOUND)
async def get_purchase(guid: str, db: AsyncSession = Depends(get_db)):
    purchase = await db.get(NoticeDatabase, guid)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return ResponseModel(status_message="found",
                                data=Notice.model_validate(purchase))

@purchase_router.delete("/{guid}", response_model = ResponseModel, status_code=status.HTTP_204_NO_CONTENT)
async def delete_purchase(guid: str, db: AsyncSession = Depends(get_db)):

    purchase = await db.get(NoticeDatabase, guid)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    await db.delete(purchase)
    await db.commit()
    return ResponseModel(status_message="deleted", data={"guid": guid})

@purchase_router.patch("/{guid}", response_model=ResponseModel, status_code=status.HTTP_200_OK)
async def update_purchase(guid: str, updated_notice: UpdateNotice, db: AsyncSession = Depends(get_db)):

    query = select(NoticeDatabase).where(NoticeDatabase.guid == guid)

    notice = await db.scalar(query)

    if not notice:
        return ResponseModel(
            status_message="not found",
            data={"guid": guid}
        )

    update_data = updated_notice.model_dump(exclude_unset=True, exclude={"guid"})
    for field, value in update_data.items():
        if value is not None:
            setattr(notice, field, value)

    try:
        await db.commit()
        await db.refresh(notice)
    except Exception:
        await db.rollback()
        raise

    return ResponseModel(
        status_message = "updated",
        data=Notice.model_validate(notice),
    )