from fastapi import HTTPException
from fastapi import APIRouter
from app.routers.dependencies import require_token, get_current_user
from app.routers.schemas import ResponseModel
from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.backend.database.settings import get_db
from app.schemas.purchase import Notice, FilterNotice, UpdateNotice
from sqlalchemy.exc import IntegrityError
from app.backend.database.crud.purchase import (put_purchase, search_purchases,
                                                get_purchase, delete_purchase, update_purchase)

purchase_router = APIRouter(prefix = "/purchases", tags=["purchases"], dependencies=[Depends(get_current_user)])

@purchase_router.post("", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
async def call_put_purchase(notice: Notice, db: AsyncSession = Depends(get_db)):
    try:
        new_purchase = await put_purchase(db, notice)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to create purchase")
    return ResponseModel(
        status_message="created",
        data=Notice.model_validate(new_purchase),
    )

@purchase_router.post("/search", response_model=ResponseModel, status_code=status.HTTP_200_OK)
async def call_search_purchases(
        filters: FilterNotice,
        db: AsyncSession = Depends(get_db)
    ):
    try:
        purchases = await search_purchases(db, filters)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to search purchases")
    return ResponseModel(status_message="found", data=purchases)

@purchase_router.get("/{guid}", response_model=ResponseModel, status_code=status.HTTP_200_OK)
async def call_get_purchase(guid: str, db: AsyncSession = Depends(get_db)):
    try:
        purchase = await get_purchase(db, guid)
        if not purchase:
            raise HTTPException(status_code=404, detail="Purchase not found")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to get purchase")
    return ResponseModel(status_message="found",
                                data=Notice.model_validate(purchase))

@purchase_router.delete("/{guid}", response_model = ResponseModel, status_code=status.HTTP_200_OK)
async def call_delete_purchase(guid: str, db: AsyncSession = Depends(get_db)):
    try:
        purchase_delete_status = await delete_purchase(db, guid)
        if not purchase_delete_status:
            raise HTTPException(status_code=404, detail="Purchase not found")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to delete purchase")
    return ResponseModel(status_message="deleted", data={"guid": guid})

@purchase_router.patch("/{guid}", response_model=ResponseModel, status_code=status.HTTP_200_OK)
async def call_update_purchase(guid: str, updated_notice: UpdateNotice, db: AsyncSession = Depends(get_db)):
    try:
        purchase_update_status = await update_purchase(db, guid, updated_notice)
        if purchase_update_status == "not found":
            raise HTTPException(status_code=404, detail="Purchase not found")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to update purchase")
    return ResponseModel(status_message="updated", data={"guid": guid})