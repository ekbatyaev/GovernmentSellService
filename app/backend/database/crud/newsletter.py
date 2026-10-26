import secrets

from sqlalchemy.exc import IntegrityError
from app.schemas.newsletter import NewsLetter, UpdateNewsLetter
from sqlalchemy.ext.asyncio import AsyncSession
from app.backend.database.models import NewsLetterDatabase, AuthCodeDatabase
from sqlalchemy import select
from datetime import datetime, timedelta
from typing import Literal
from app.schemas.newsletter import NewsLetter, FilterNewsLetters, ConfirmOptionNewsLetter
from app.settings import MOSCOW_TZ

async def put_newsletter(db: AsyncSession, newsletter: NewsLetter) -> NewsLetterDatabase:
    new_newsletter = NewsLetterDatabase(**newsletter.model_dump())
    db.add(new_newsletter)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise
    await db.refresh(new_newsletter)
    return new_newsletter

async def search_newsletters(db: AsyncSession, filters: FilterNewsLetters) -> list[NewsLetter]:
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
    return data

async def get_newsletter(db: AsyncSession, guid: str) -> NewsLetter | None:
    newsletter = await db.get(NewsLetterDatabase, guid)
    return newsletter

async def delete_newsletter(db: AsyncSession, guid: str) -> bool:
    newsletter = await db.get(NewsLetterDatabase, guid)
    if not newsletter:
        return False
    await db.delete(newsletter)
    await db.commit()
    return True

async def update_newsletter(db: AsyncSession, guid: str, updated_newsletter: UpdateNewsLetter) -> Literal["not found", "updated"]:
    query = select(NewsLetterDatabase).where(NewsLetterDatabase.guid == guid)

    newsletter = await db.scalar(query)

    if not newsletter:
        return "not found"

    update_data = updated_newsletter.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(newsletter, field, value)

    try:
        await db.commit()
        await db.refresh(newsletter)
    except IntegrityError:
        await db.rollback()
        raise

    return "updated"

async def confirm_newsletter(db: AsyncSession, option_newsletter_data:
ConfirmOptionNewsLetter) -> Literal["not found", "expired", "too many attempts", "invalid", "failed", "deleted", "created"]:
    query = select(AuthCodeDatabase)
    query = query.where(AuthCodeDatabase.guid == option_newsletter_data.guid)

    search_request = await db.execute(query)
    auth_code = search_request.scalar_one_or_none()

    if not auth_code:
        return "not found"

    time_now = datetime.now(MOSCOW_TZ).replace(tzinfo=None)

    if time_now - auth_code.created_at <= timedelta(minutes=5):
        await db.delete(auth_code)
        await db.commit()

        return "expired"

    if time_now - auth_code.last_checked_at <= timedelta(seconds=20):
        return "too many attempts"

    auth_code.last_checked_at = time_now
    await db.commit()

    if not secrets.compare_digest(str(option_newsletter_data.code).encode(), str(auth_code.code).encode()):
        return "invalid"

    if option_newsletter_data.option == "subscribe":
        new_newsletter = NewsLetterDatabase(guid=option_newsletter_data.guid,
                                            email=option_newsletter_data.email,
                                            filter_type_name=option_newsletter_data.filter_type_name,
                                            district_name=option_newsletter_data.district_name)

        try:
            db.add(new_newsletter)
            await db.commit()
            await db.refresh(new_newsletter)
            return "created"
        except IntegrityError:
            await db.rollback()
            return "failed"

    elif option_newsletter_data.option == "unsubscribe":
        newsletter = await db.get(NewsLetterDatabase, option_newsletter_data.guid)
        if not newsletter:
            return "not found"
        await db.delete(newsletter)
        await db.commit()
        return "deleted"
    else:
        return "invalid"