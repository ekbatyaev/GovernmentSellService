from fastapi import HTTPException
from fastapi import APIRouter
from app.routers.dependencies import get_current_user
from app.routers.schemas import ResponseModel
from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.backend.database.settings import get_db
from app.schemas.newsletter import (NewsLetter, FilterNewsLetters,
                                    UpdateNewsLetter, ConfirmOptionNewsLetter)
from sqlalchemy.exc import IntegrityError
from app.backend.database.crud.newsletter import (put_newsletter, search_newsletters,
                                                  get_newsletter, delete_newsletter,
                                                  update_newsletter, confirm_newsletter)

newsletter_router = APIRouter(prefix="/newsletters", tags=["newsletters"], dependencies=[Depends(get_current_user)])

@newsletter_router.post("", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
async def call_put_newsletter(newsletter: NewsLetter, db: AsyncSession = Depends(get_db)):
    try:
        new_newsletter = await put_newsletter(db, newsletter)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to create newsletter")
    return ResponseModel(
        status_message="created",
        data=NewsLetter.model_validate(new_newsletter),
    )

@newsletter_router.get("/{guid}", response_model=ResponseModel, status_code=status.HTTP_200_OK)
async def call_get_newsletter(guid: str, db: AsyncSession = Depends(get_db)):
    try:
        newsletter = await get_newsletter(db, guid)
        if not newsletter:
            raise HTTPException(status_code=404, detail="Newsletter not found")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to get newsletter")
    return ResponseModel(status_message="found",
                                data=NewsLetter.model_validate(newsletter))

@newsletter_router.delete("/{guid}", response_model = ResponseModel, status_code=status.HTTP_200_OK)
async def call_delete_newsletter(guid: str, db: AsyncSession = Depends(get_db)):
    try:
        newsletter_delete_status = await delete_newsletter(db, guid)
        if not newsletter_delete_status:
            raise HTTPException(status_code=404, detail="Newsletter not found")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to delete newsletter")
    return ResponseModel(status_message="deleted", data={"guid": guid})

@newsletter_router.patch("/{guid}", response_model=ResponseModel, status_code=status.HTTP_200_OK)
async def call_update_newsletter(guid: str, updated_newsletter: UpdateNewsLetter, db: AsyncSession = Depends(get_db)):
    try:
        newsletter_update_status = await update_newsletter(db, guid, updated_newsletter)
        if newsletter_update_status == "not found":
            raise HTTPException(status_code=404, detail="Newsletter not found")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to update newsletter")
    return ResponseModel(status_message="updated", data={"guid": guid})

@newsletter_router.post("/search", response_model=ResponseModel, status_code=status.HTTP_200_OK)
async def call_search_newsletters(
        filters: FilterNewsLetters,
        db: AsyncSession = Depends(get_db)
    ):
    try:
        newsletters = await search_newsletters(db, filters)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to search newsletters")
    return ResponseModel(status_message="found", data=newsletters)

@newsletter_router.post("/confirm", response_model=ResponseModel, status_code=status.HTTP_200_OK)
async def call_confirm_newsletter(option_newsletter_data: ConfirmOptionNewsLetter, db: AsyncSession = Depends(get_db)):
    try:
        newsletter_confirm_status = await confirm_newsletter(db, option_newsletter_data)
        if newsletter_confirm_status == "created":
            return ResponseModel(status_message="created", data={"guid": option_newsletter_data.guid})
        elif newsletter_confirm_status == "deleted":
            return ResponseModel(status_message="deleted", data={"guid": option_newsletter_data.guid})
        elif newsletter_confirm_status == "not found":
            raise HTTPException(status_code=500, detail="Not found")
        elif newsletter_confirm_status == "expired":
            raise HTTPException(status_code=429, detail="The code is expired")
        elif newsletter_confirm_status == "too many attempts":
            raise HTTPException(status_code=429, detail="Too many attempts, try again later")
        elif newsletter_confirm_status == "invalid":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code")
        elif newsletter_confirm_status == "failed":
            raise HTTPException(status_code=400, detail="Failed to create newsletter")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to create newsletter")