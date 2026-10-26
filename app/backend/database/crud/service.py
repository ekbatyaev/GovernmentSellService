import uuid
from random import randint
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.backend.database.models import AuthCodeDatabase
from sqlalchemy import select
from datetime import datetime, timedelta
from app.settings import logger, MOSCOW_TZ
from app.backend.functions.functions import send_email
from app.schemas.service import AuthCode, StatusAuthCode, FilterAuthCode, UpdateAuthCode
from typing import Literal

async def put_auth_code(db: AsyncSession, auth_code: AuthCode) -> AuthCodeDatabase:
    new_auth_code = AuthCodeDatabase(**auth_code.model_dump())
    db.add(new_auth_code)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise
    await db.refresh(new_auth_code)
    return new_auth_code

async def get_auth_code(db: AsyncSession, guid: str) -> AuthCode | None:
    auth_code = await db.get(AuthCodeDatabase, guid)
    return auth_code

async def delete_auth_code(db: AsyncSession, guid: str) -> bool:
    auth_code = await db.get(AuthCodeDatabase, guid)
    if not auth_code:
        return False
    await db.delete(auth_code)
    await db.commit()
    return True

async def update_auth_code(db: AsyncSession, guid: str, updated_auth_code: UpdateAuthCode) -> Literal["not found", "updated"]:
    try:
        auth_code = await get_auth_code(db, guid)
    except IntegrityError as e:
        logger.exception(f"Произошла ошибка при сохранении кода: {e}")
        raise

    if not auth_code:
        return "not found"

    update_data = updated_auth_code.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(auth_code, field, value)

    try:
        await db.commit()
        await db.refresh(auth_code)
    except IntegrityError:
        await db.rollback()
        raise

    return "updated"

async def search_auth_codes(db: AsyncSession, filters: FilterAuthCode) -> list[AuthCode]:
    query = select(AuthCodeDatabase)

    if filters.email:
        query = query.where(AuthCodeDatabase.email == filters.email)

    if filters.created_at_from:
        query = query.where(AuthCodeDatabase.created_at >= filters.created_at_from)

    if filters.created_at_to:
        query = query.where(AuthCodeDatabase.created_at <= filters.created_at_to.date())

    if filters.last_checked_at_from:
        query = query.where(AuthCodeDatabase.last_checked_at >= filters.last_checked_at_from)

    if filters.last_checked_at_to:
        query = query.where(AuthCodeDatabase.last_checked_at <= filters.last_checked_at_to)

    query = query.order_by(AuthCodeDatabase.created_at.desc().nullslast())

    result = await db.execute(query)
    auth_codes = result.scalars().all()
    data = [AuthCode.model_validate(a) for a in auth_codes]
    return data

async def send_auth_code(db: AsyncSession, email: str) -> StatusAuthCode:
    created_at_to = datetime.now(MOSCOW_TZ).replace(tzinfo=None) - timedelta(minutes=5)
    try:
        auth_codes = await search_auth_codes(db, FilterAuthCode(email=email, created_at_to=created_at_to))
    except IntegrityError as e:
        logger.exception(f"Произошла ошибка получения данных кодов: {e}")
        raise

    if auth_codes:
        return StatusAuthCode(status_message="try later")

    code = randint(100000, 999999)

    try:
        subject = "Проверочный код"
        html_content = f"""
                <html>
                  <body style="font-family: Arial, sans-serif; line-height: 1.5; color: #333;">
                    <h2 style="color:#2E86C1;">Проверочный код для рассылки Systeme.закупки</h2>
                    <p>Здравствуйте!</p>
                    <p>Ваш проверочный код:</p>
                    <p style="font-size: 1.5em; font-weight: bold; color:#E74C3C;">{code}</p>
                    <p>Введите этот код в приложении, чтобы подтвердить действие.</p>
                    <hr>
                    <p style="font-size: 0.9em; color:#888;">
                      Это письмо сформировано автоматически, отвечать на него не нужно.
                    </p>
                  </body>
                </html>
                """

        await send_email(
            email,
            subject,
            html_content
        )
    except Exception:
        return StatusAuthCode(status_message="not found")

    auth_code_guid = str(uuid.uuid4())
    auth_code = AuthCode(guid=auth_code_guid, email=email,
                                     code=code, created_at=datetime.now(MOSCOW_TZ).replace(tzinfo=None),
                                     last_checked_at=datetime.now(MOSCOW_TZ).replace(tzinfo=None))
    try:
        await put_auth_code(db, auth_code)
        return StatusAuthCode(status_message="created", guid=auth_code_guid)
    except IntegrityError as e:
        logger.exception(f"Произошла ошибка при сохранении кода: {e}")
        return StatusAuthCode(status_message="not saved")