from random import randint
from app.backend.functions import send_email, set_auth_code, pop_auth_code
from fastapi import HTTPException
from fastapi import APIRouter
from app.routers.dependencies import require_token
from app.routers.schemas import ResponseModel
from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.backend.db.settings import get_db
from app.schemas.email import NewsLetter
from app.routers.email.schemas import FilterNewsLetters
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.backend.db.models import NewsLetterDatabase
from app.routers.email.schemas import UpdateNewsLetter, VerifyCodeNewsLetter

email_router = APIRouter(prefix = "/email", tags=["email"], dependencies=[Depends(require_token)])

@email_router.post("", response_model = ResponseModel, status_code=status.HTTP_201_CREATED)
async def put_newsletter(newsletter: NewsLetter, db: AsyncSession = Depends(get_db)):

    new_newsletter = NewsLetter(**newsletter.model_dump())

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

@email_router.get("", response_model=ResponseModel, status_code=status.HTTP_302_FOUND)
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

@email_router.get("/{guid}", response_model=ResponseModel, status_code=status.HTTP_302_FOUND)
async def get_newsletter(guid: str, db: AsyncSession = Depends(get_db)):
    newsletter = await db.get(NewsLetterDatabase, guid)
    if not newsletter:
        raise HTTPException(status_code=404, detail="Newsletter not found")
    return ResponseModel(status_message="found",
                                data=NewsLetter.model_validate(newsletter))

@email_router.delete("/{guid}", response_model = ResponseModel, status_code=status.HTTP_204_NO_CONTENT)
async def delete_newsletter(guid: str, db: AsyncSession = Depends(get_db)):
    newsletter = await db.get(NewsLetterDatabase, guid)
    if not newsletter:
        raise HTTPException(status_code=404, detail="Newsletter not found")
    await db.delete(newsletter)
    await db.commit()
    return ResponseModel(status_message="deleted", data={"guid": guid})

@email_router.patch("/{guid}", response_model=ResponseModel, status_code=status.HTTP_200_OK)
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

@email_router.post("/send_auth_code/{email}", response_model=ResponseModel, status_code=status.HTTP_200_OK)
async def send_auth_code(email: str, db: AsyncSession = Depends(get_db)):
    code = randint(100000, 999999)

    try:
        subject = "Проверочный код"
        html_content = f"""
        <html>
          <body style="font-family: Arial, sans-serif; line-height: 1.5; color: #333;">
            <h2 style="color:#2E86C1;">Проверочный код для рассылки Госзакупок</h2>
            <p>Здравствуйте!</p>
            <p>Ваш проверочный код для вашего email:</p>
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
        raise HTTPException(status_code=500, detail="Email not found")

    try:
        await set_auth_code(db, email, code)
    except Exception:
        raise HTTPException(status_code=500, detail="Code not saved")

    return ResponseModel(
        status_message="success",
        data={"email": email}
    )


@email_router.post("/verify_code/{email}", response_model=ResponseModel, status_code=status.HTTP_204_NO_CONTENT)
async def verify_code(email: str, data: VerifyCodeNewsLetter, db: AsyncSession = Depends(get_db)):

    try:
        real_code = await pop_auth_code(db, email)
    except Exception:
        raise HTTPException(status_code=500, detail="Code data is not available")

    if real_code is None:
        raise HTTPException(status_code=404, detail="Code not found")

    if real_code != data.code:
        raise HTTPException(status_code=400, detail="Invalid code")

    return ResponseModel(
        status_message="success",
        data={"auth": True}
    )