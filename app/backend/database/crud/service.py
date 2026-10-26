import uuid
from random import randint
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.backend.database.models import AuthCodeDatabase
from sqlalchemy import select
from datetime import datetime, timedelta
from app.settings import MOSCOW_TZ
from app.backend.functions import send_email
from app.schemas.service import StatusAuthCode

async def send_auth_code(db: AsyncSession, email: str) -> StatusAuthCode:
    query = select(AuthCodeDatabase)
    query = query.where(AuthCodeDatabase.email == email)

    query = query.where(
        AuthCodeDatabase.created_at <= datetime.now(MOSCOW_TZ).replace(tzinfo=None) - timedelta(minutes=5))

    search_request = await db.execute(query)
    earlier_auth_code = search_request.scalar_one_or_none()

    if earlier_auth_code:
        return StatusAuthCode(status_message="try later")

    code = randint(100000, 999999)

    try:
        subject = "Проверочный код"
        html_content = f"""
                <html>
                  <body style="font-family: Arial, sans-serif; line-height: 1.5; color: #333;">
                    <h2 style="color:#2E86C1;">Проверочный код для рассылки Госзакупок</h2>
                    <p>Здравствуйте!</p>
                    <p>Ваш проверочный код для вашего newsletters:</p>
                    <p style="font-size: 1.5em; font-weight: bold; color:#E74C3C;">{code}</p>
                    <p>Введите этот код в приложении, чтобы подтвердить или отменить рассылку.</p>
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
    new_auth_code = AuthCodeDatabase(guid=auth_code_guid, email=email,
                                     code=code, created_at=datetime.now(MOSCOW_TZ).replace(tzinfo=None),
                                     last_checked_at=datetime.now(MOSCOW_TZ).replace(tzinfo=None))

    try:
        db.add(new_auth_code)
        await db.commit()
        await db.refresh(new_auth_code)
        return StatusAuthCode(status_message="created", guid=auth_code_guid)
    except IntegrityError:
        await db.rollback()
        return StatusAuthCode(status_message="not saved")