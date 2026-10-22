import secrets
from datetime import datetime, timedelta
from app.settings import MOSCOW_TZ
from fastapi import HTTPException
from fastapi import APIRouter
from app.routers.dependencies import require_token
from app.routers.schemas import ResponseModel
from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.backend.db.settings import get_db
from app.schemas.email import NewsLetter
from app.routers.newsletters.schemas import FilterNewsLetters
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.backend.db.models import NewsLetterDatabase, AuthCodeDatabase
from app.routers.newsletters.schemas import UpdateNewsLetter, ConfirmOptionNewsLetter

newsletter_router = APIRouter(prefix ="/newsletters", tags=["newsletters"], dependencies=[Depends(require_token)])

@newsletter_router.post("", response_model = ResponseModel, status_code=status.HTTP_201_CREATED)
async def put_newsletter(newsletter: NewsLetter, db: AsyncSession = Depends(get_db)):
    new_newsletter = NewsLetterDatabase(**newsletter.model_dump())

    try:
        db.add(new_newsletter)
        await db.commit()
        await db.refresh(new_newsletter)
        return ResponseModel(
            status_message="created",
            data=NewsLetter.model_validate(new_newsletter)
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Failed to create newsletter")

@newsletter_router.get("", response_model=ResponseModel, status_code=status.HTTP_302_FOUND)
async def search_newsletters(
        filters: FilterNewsLetters,
        db: AsyncSession = Depends(get_db)
    ):
    query = select(NewsLetterDatabase)

    if filters.list_emails:
        query = query.where(NewsLetterDatabase.email.in_(filters.list_emails))

    if filters.list_filter_type_names:
        query = query.where(NewsLetterDatabase.filter_type_name.in_(filters.list_filter_type_names))

    if filters.list_district_names:
        query = query.where(NewsLetterDatabase.district_name.in_(filters.list_district_names))

    query = query.order_by(NewsLetterDatabase.email.asc())

    result = await db.execute(query)
    newsletters = result.scalars().all()
    data = [NewsLetter.model_validate(n) for n in newsletters]
    return ResponseModel(status_message="found", data=data)

@newsletter_router.get("/{guid}", response_model=ResponseModel, status_code=status.HTTP_302_FOUND)
async def get_newsletter(guid: str, db: AsyncSession = Depends(get_db)):
    newsletter = await db.get(NewsLetterDatabase, guid)
    if not newsletter:
        raise HTTPException(status_code=404, detail="Newsletter not found")
    return ResponseModel(status_message="found",
                                data=NewsLetter.model_validate(newsletter))

@newsletter_router.delete("/{guid}", response_model = ResponseModel, status_code=status.HTTP_204_NO_CONTENT)
async def delete_newsletter(guid: str, db: AsyncSession = Depends(get_db)):
    newsletter = await db.get(NewsLetterDatabase, guid)
    if not newsletter:
        raise HTTPException(status_code=404, detail="Newsletter not found")
    await db.delete(newsletter)
    await db.commit()
    return ResponseModel(status_message="deleted", data={"guid": guid})

@newsletter_router.patch("/{guid}", response_model=ResponseModel, status_code=status.HTTP_200_OK)
async def update_newsletter(guid: str, updated_newsletter: UpdateNewsLetter, db: AsyncSession = Depends(get_db)):

    query = select(NewsLetterDatabase).where(NewsLetterDatabase.guid == guid)

    newsletter = await db.scalar(query)

    if not newsletter:
        return ResponseModel(
            status_message="not found",
            data={"guid": guid}
        )

    update_data = updated_newsletter.model_dump(exclude_unset=True, exclude={"guid"})
    for field, value in update_data.items():
        if value is not None:
            setattr(newsletter, field, value)

    try:
        await db.commit()
        await db.refresh(newsletter)
    except Exception:
        await db.rollback()
        raise

    return ResponseModel(
        status_message = "updated",
        data=NewsLetter.model_validate(newsletter),
    )

@newsletter_router.post("/confirm", response_model=ResponseModel, status_code=status.HTTP_200_OK)
async def confirm_newsletter(option_newsletter_data: ConfirmOptionNewsLetter, db: AsyncSession = Depends(get_db)):

    query = select(AuthCodeDatabase)
    query = query.where(AuthCodeDatabase.guid == option_newsletter_data.guid)

    search_request = await db.execute(query)
    auth_code = search_request.scalar_one_or_none()

    if not auth_code:
        raise HTTPException(status_code=500, detail="Not found")

    time_now = datetime.now(MOSCOW_TZ).replace(tzinfo=None)

    if time_now - auth_code.created_at <= timedelta(minutes=5):

        await db.delete(auth_code)
        await db.commit()

        raise HTTPException(status_code=429, detail="The code is expired")

    if time_now - auth_code.last_checked_at <= timedelta(seconds=20):
        raise HTTPException(status_code=429, detail="Too many attempts, try again later")

    auth_code.last_checked_at = time_now
    await db.commit()

    if secrets.compare_digest(str(option_newsletter_data.code).encode(), str(auth_code.code).encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code")

    if option_newsletter_data.option == "subscribe":
        new_newsletter = NewsLetterDatabase(guid = option_newsletter_data.guid,
                                            email = option_newsletter_data.email,
                                            filter_type_name = option_newsletter_data.filter_type_name,
                                            district_name = option_newsletter_data.district_name)

        try:
            db.add(new_newsletter)
            await db.commit()
            await db.refresh(new_newsletter)
            return ResponseModel(
                status_message="created",
                data=NewsLetter.model_validate(new_newsletter)
            )
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=400, detail="Failed to create newsletter")

    elif option_newsletter_data.option == "unsubscribe":
        newsletter = await db.get(NewsLetterDatabase, option_newsletter_data.guid)
        if not newsletter:
            raise HTTPException(status_code=404, detail="Newsletter not found")
        await db.delete(newsletter)
        await db.commit()
        return ResponseModel(status_message="deleted", data={"guid": option_newsletter_data.guid})
    else:
        raise HTTPException(status_code=429, detail="Invalid option")