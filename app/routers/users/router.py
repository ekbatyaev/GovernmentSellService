from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
import uuid
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from app.routers.dependencies import (require_admin, get_current_user, hash_password)
from sqlalchemy.ext.asyncio import AsyncSession
from app.routers.schemas import ResponseModel
from app.routers.users.schemas import ConfirmEmailUser, RegisterUser, ApproveUser
from app.backend.database.settings import get_db
from app.backend.database.models import UserDatabase
from app.schemas.user import User, UpdateUser, FilterUser, LoginUser, RecoverPasswordUser, ChangePasswordUser
from app.dependencies import verify_password
from app.schemas.service import StatusAuthCode
from app.backend.email.functions import send_email
from app.backend.database.crud.service import check_auth_code, send_auth_code, delete_auth_code
from app.backend.database.crud.user import put_user, get_user, delete_user, update_user, login_user, search_users
from app.settings import logger, settings, MOSCOW_TZ

users_router = APIRouter(prefix="/users", tags=["users"])

@users_router.post("", response_model=ResponseModel, status_code=status.HTTP_201_CREATED,
                   dependencies=[Depends(require_admin)])
async def call_put_user(user: User, db: AsyncSession = Depends(get_db)):
    try:
        new_user = await put_user(db, user)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to create user")
    return ResponseModel(
        status_message="created",
        data=User.model_validate(new_user),
    )


@users_router.get("/{guid}", response_model=ResponseModel,
                  status_code=status.HTTP_200_OK)
async def call_get_user(guid: str, db: AsyncSession = Depends(get_db),
                        current_user: UserDatabase = Depends(get_current_user)):
    if guid != current_user.guid and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="You are not allowed to see user info")

    try:
        user = await get_user(db, guid)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to get user")
    return ResponseModel(status_message="found",
                                data=User.model_validate(user))

@users_router.delete("/{guid}", response_model=ResponseModel,
                     status_code=status.HTTP_200_OK)
async def call_delete_user(guid: str, db: AsyncSession = Depends(get_db),
                           current_user: UserDatabase = Depends(get_current_user)):
    if guid != current_user.guid and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="You are not allowed to see user info")

    try:
        user_delete_status = await delete_user(db, guid)
        if not user_delete_status:
            raise HTTPException(status_code=404, detail="User not found")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to delete user")
    return ResponseModel(status_message="deleted", data={"guid": guid})

@users_router.patch("/{guid}", response_model=ResponseModel, status_code=status.HTTP_200_OK)
async def call_update_user(guid: str, updated_user: UpdateUser,
                      db: AsyncSession = Depends(get_db), current_user: UserDatabase = Depends(get_current_user)):
    if (guid != current_user.guid and current_user.role != "admin") or current_user.role == "guest":
        raise HTTPException(status_code=403, detail="You are not allowed to change user info")

    updated_data = updated_user.model_dump(exclude_unset=True, exclude_none=True)
    if current_user.role != "admin":
        updated_data.pop("role", None)
        updated_data.pop("email", None)
        # Свой пароль пользователь меняет только через /users/password_change (с проверкой текущего)
        updated_data.pop("password", None)
    if "password" in updated_data:
        updated_data["password"] = hash_password(updated_data["password"])

    try:
        user_update_status = await update_user(db, guid, UpdateUser(**updated_data))
        if user_update_status == "not found":
            raise HTTPException(status_code=404, detail="User not found")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to update user")
    return ResponseModel(status_message="updated", data={"guid": guid})

@users_router.post("/password_change", response_model=ResponseModel, status_code=status.HTTP_200_OK)
async def call_change_password(change_pass_user: ChangePasswordUser, db: AsyncSession = Depends(get_db),
                               current_user: UserDatabase = Depends(get_current_user)):
    if not verify_password(change_pass_user.current_password, current_user.password):
        raise HTTPException(status_code=400, detail="Invalid current password")

    try:
        user_update_status = await update_user(db, current_user.guid,
                                               UpdateUser(password=hash_password(change_pass_user.new_password)))
        if user_update_status == "not found":
            raise HTTPException(status_code=404, detail="User not found")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to update user password")

    return ResponseModel(status_message="updated", data={})

@users_router.post("/login", response_model=ResponseModel, status_code=status.HTTP_200_OK)
async def call_login_user(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    try:
        user_login: LoginUser = await login_user(db, form.username, form.password)
        if user_login.status == "invalid":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to login")

    return ResponseModel(
        status_message="updated",
        data={"access_token": user_login.payload, "token_type": "bearer"}
    )

@users_router.post("/confirm", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
async def call_confirm_user(confirm_email_user: ConfirmEmailUser, db: AsyncSession = Depends(get_db)):
    try:
        users: list[User] = await search_users(db, FilterUser(email=str(confirm_email_user.email)))
        if users:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to confirm user")

    try:
        send_auth_code_status: StatusAuthCode = await send_auth_code(db, str(confirm_email_user.email))
        if send_auth_code_status.status_message == "created":
            return ResponseModel(
                status_message="created",
                data={"guid": send_auth_code_status.guid}
            )
        elif send_auth_code_status.status_message == "not saved":
            raise HTTPException(status_code=500, detail="Code not saved")
        elif send_auth_code_status.status_message == "not found":
            raise HTTPException(status_code=500, detail="Not found")
        elif send_auth_code_status.status_message == "try later":
            raise HTTPException(status_code=500,
                                detail="Подождите 5 минут перед тем как отправить другой проверочный код.")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to send auth code")

@users_router.post("/password_recover", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
async def call_send_recover_code(confirm_email_user: ConfirmEmailUser, db: AsyncSession = Depends(get_db)):
    try:
        users: list[User] = await search_users(db, FilterUser(email=str(confirm_email_user.email)))
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to get user")
    if not users:
        raise HTTPException(status_code=404, detail="User not found")
    if users[0].role == "guest":
        raise HTTPException(status_code=403, detail="You are not allowed to change user info")

    try:
        send_auth_code_status: StatusAuthCode = await send_auth_code(db, str(confirm_email_user.email))
        if send_auth_code_status.status_message == "created":
            return ResponseModel(
                status_message="created",
                data={"guid": send_auth_code_status.guid}
            )
        elif send_auth_code_status.status_message == "not saved":
            raise HTTPException(status_code=500, detail="Code not saved")
        elif send_auth_code_status.status_message == "not found":
            raise HTTPException(status_code=500, detail="Not found")
        elif send_auth_code_status.status_message == "try later":
            raise HTTPException(status_code=500,
                                detail="Подождите 5 минут перед тем как отправить другой проверочный код.")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to send auth code")

@users_router.post("/password_recover/{auth_code_guid}", response_model=ResponseModel,
                   status_code=status.HTTP_200_OK)
async def call_recover_password(auth_code_guid: str, recover_pass_user: RecoverPasswordUser,
                                db: AsyncSession = Depends(get_db)):
    try:
        users: list[User] = await search_users(db, FilterUser(email=str(recover_pass_user.email)))
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to get user")
    if not users:
        raise HTTPException(status_code=404, detail="User not found")
    if users[0].role == "guest":
        raise HTTPException(status_code=403, detail="You are not allowed to change user info")

    current_user = users[0]

    try:
        auth_code_confirm_status = await check_auth_code(db, auth_code_guid, recover_pass_user.code,
                                                         str(current_user.email))
        if auth_code_confirm_status == "not found":
            raise HTTPException(status_code=500, detail="Not found auth code")
        elif auth_code_confirm_status == "expired":
            raise HTTPException(status_code=429, detail="The code is expired")
        elif auth_code_confirm_status == "too many attempts":
            raise HTTPException(status_code=429, detail="Too many attempts, try again later")
        elif auth_code_confirm_status == "invalid":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to check auth code")

    delete_auth_code_status = await delete_auth_code(db, auth_code_guid)

    if not delete_auth_code_status:
        raise HTTPException(status_code=429, detail="The code is not deleted")

    try:
        user_update_status = await update_user(db, current_user.guid,
                                               UpdateUser(password=hash_password(recover_pass_user.password)))
        if user_update_status == "not found":
            raise HTTPException(status_code=404, detail="User not found")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to update user password")

    return ResponseModel(status_message="updated", data={})


@users_router.post("/register/{auth_code_guid}", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
async def call_register_user(auth_code_guid: str, register_user: RegisterUser, db: AsyncSession = Depends(get_db)):
    try:
        auth_code_confirm_status = await check_auth_code(db, auth_code_guid,
                                                         register_user.code, str(register_user.email))
        if auth_code_confirm_status == "not found":
            raise HTTPException(status_code=500, detail="Not found auth code")
        elif auth_code_confirm_status == "expired":
            raise HTTPException(status_code=429, detail="The code is expired")
        elif auth_code_confirm_status == "too many attempts":
            raise HTTPException(status_code=429, detail="Too many attempts, try again later")
        elif auth_code_confirm_status == "invalid":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to check auth code")

    delete_auth_code_status = await delete_auth_code(db, auth_code_guid)

    if not delete_auth_code_status:
        raise HTTPException(status_code=429, detail="The code is not deleted")

    new_user_guid = str(uuid.uuid4())

    new_user_info = User(
        guid=new_user_guid,
        email=register_user.email,
        password=hash_password(register_user.password),
        role="guest",
        created_at=datetime.now(MOSCOW_TZ).replace(tzinfo=None),
    )

    try:
        await put_user(db, new_user_info)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to create user")

    approve_link = f"{settings.app_web_open_url}/approve/{new_user_guid}"

    body = f"""\
        <div style="font-family:Segoe UI,Arial,sans-serif;font-size:15px;color:#111827;max-width:480px;">
          <p>Новый пользователь ждёт подтверждения:<br>
             <b>{register_user.email}</b></p>
          <p><a href="{approve_link}" style="display:inline-block;padding:10px 24px;background:#2563eb;color:#fff;
             text-decoration:none;border-radius:6px;font-weight:600;">Подтвердить</a></p>
          <p style="font-size:12px;color:#6b7280;">Если кнопка не работает:
          <a href="{approve_link}">{approve_link}</a></p>
        </div>"""

    try:
        await send_email(settings.supervisor_system_email, "Подтверждение регистрации пользователя",
                         body)
    except Exception as e:
        logger.exception(f"Ошибка: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="The mail server is not available right now. Please, try later.")

    return ResponseModel(status_message="created", data={"guid": new_user_guid})


@users_router.post("/approve/{guid}", status_code=status.HTTP_200_OK, dependencies=[Depends(require_admin)])
async def call_approve_user(guid: str, approve_data: ApproveUser, db: AsyncSession = Depends(get_db)):
    try:
        user: User | None = await get_user(db, guid)
        if user is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is not exists")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to confirm user")

    updated_data = approve_data.model_dump(exclude_unset=True, exclude_none=True)

    try:
        user_update_status = await update_user(db, guid, UpdateUser(**updated_data))
        if user_update_status == "not found":
            raise HTTPException(status_code=404, detail="User not found")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to update user")

    body = f"""\
        <div style="font-family:Segoe UI,Arial,sans-serif;font-size:15px;color:#111827;max-width:480px;">
          <p>Ваша учетная запись подтверждена - Добро пожаловать в систему!</p>
        </div>"""

    try:
        await send_email(user.email, "Подтверждение регистрации пользователя",
                         body)
    except Exception as e:
        logger.exception(f"Ошибка: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="The mail server is not available right now. Please, try later.")
    return ResponseModel(
        status_message="approved",
        data={}
    )
