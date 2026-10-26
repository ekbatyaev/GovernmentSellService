from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
import uuid
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.routers.dependencies import (require_admin, get_current_user,
                                      verify_password, create_access_token, hash_password)
from sqlalchemy.ext.asyncio import AsyncSession
from app.routers.schemas import ResponseModel
from app.routers.users.schemas import UpdateUser, RegisterUser, ApproveUser
from app.backend.database.settings import get_db
from app.backend.database.models import UserDatabase
from app.schemas.user import User
from app.backend.email.functions import send_email
from app.settings import settings, MOSCOW_TZ

users_router = APIRouter(prefix="/users", tags=["users"])

@users_router.get("/{guid}", response_model=ResponseModel,
                  status_code=status.HTTP_302_FOUND, dependencies=[Depends(require_admin)])
async def get_user(guid: str, db: AsyncSession = Depends(get_db)):
    user = await db.get(UserDatabase, guid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return ResponseModel(status_message="found",
                                data=User.model_validate(user))

@users_router.delete("/{guid}", response_model = ResponseModel,
                     status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def delete_user(guid: str, db: AsyncSession = Depends(get_db)):

    user = await db.get(UserDatabase, guid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(user)
    await db.commit()
    return ResponseModel(status_message="deleted", data={"guid": guid})

@users_router.patch("/{guid}", response_model=ResponseModel, status_code=status.HTTP_200_OK)
async def update_user(guid: str, updated_user: UpdateUser,
                      db: AsyncSession = Depends(get_db), user: UserDatabase = Depends(get_current_user)):

    if guid != user.guid and user.role != "admin":
        raise HTTPException(status_code=403, detail="You are not allowed to change user info")

    query = select(UserDatabase).where(UserDatabase.guid == guid)

    user = await db.scalar(query)

    if not user:
        return ResponseModel(
            status_message="not found",
            data={"guid": guid}
        )

    update_data = updated_user.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(user, field, value)

    try:
        await db.commit()
        await db.refresh(user)
    except Exception:
        await db.rollback()
        raise

    return ResponseModel(
        status_message = "updated",
        data=User.model_validate(user)
    )

@users_router.post("/login", response_model=ResponseModel, status_code=status.HTTP_200_OK)
async def login_user(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserDatabase).where(UserDatabase.email == form.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(form.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    return ResponseModel(
        status_message="updated",
        data={"access_token": create_access_token(user), "token_type": "bearer"}
    )

@users_router.post("/register", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
async def register(register_user: RegisterUser, db: AsyncSession = Depends(get_db)):

    result = await db.execute(select(UserDatabase).where(UserDatabase.email == register_user.email))

    user = result.scalar_one_or_none()

    if user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    new_user_guid = str(uuid.uuid4())

    new_user = UserDatabase(
        guid=new_user_guid,
        email=register_user.email,
        password=hash_password(register_user.password),
        role="guest",
        created_at=datetime.now(MOSCOW_TZ).replace(tzinfo=None),
    )

    try:
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
    except IntegrityError:  # два одновременных запроса с одним email
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    approve_link = f"{settings.app_web_open_url}/approve/{new_user_guid}"

    body = f"""\
    <div style="font-family:Segoe UI,Arial,sans-serif;font-size:15px;color:#111827;max-width:480px;">
      <p>Новый пользователь ждёт подтверждения:<br>
         <b>{register_user.email}</b></p>
      <p><a href="{approve_link}" style="display:inline-block;padding:10px 24px;background:#2563eb;color:#fff;
         text-decoration:none;border-radius:6px;font-weight:600;">Подтвердить</a></p>
      <p style="font-size:12px;color:#6b7280;">Если кнопка не работает: <a href="{approve_link}">{approve_link}</a></p>
    </div>"""

    try:
        await send_email(settings.smtp_supervisor_system_email, "Подтверждение регистрации пользователя",
                               body)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="The mail server is not available right now. Please, try later.")

    return ResponseModel(
        status_message="success",
        data={}
    )

@users_router.post("/approve/{guid}", status_code=status.HTTP_200_OK, dependencies=[Depends(require_admin)])
async def approve_user(guid: str, approve_data: ApproveUser, db: AsyncSession = Depends(get_db)):

    result = await db.execute(select(UserDatabase).where(UserDatabase.guid == guid))

    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is not exists")

    update_data = approve_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(user, field, value)
    try:
        await db.commit()
        await db.refresh(user)
    except Exception:
        await db.rollback()
        raise

    body = f"""\
        <div style="font-family:Segoe UI,Arial,sans-serif;font-size:15px;color:#111827;max-width:480px;">
          <p>Ваша учетная запись подтверждена - Добро пожаловать в систему!</p>
        </div>"""

    try:
        await send_email(user.email, "Подтверждение регистрации пользователя",
                         body)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="The mail server is not available right now. Please, try later.")
    return ResponseModel(
        status_message="approved",
        data={}
    )