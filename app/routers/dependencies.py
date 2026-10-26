import secrets
from datetime import datetime, timedelta
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession
from app.settings import settings, MOSCOW_TZ
from app.backend.database.models import UserDatabase
from app.backend.database.settings import get_db
from app.schemas.user import User

password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(user: UserDatabase) -> str:
    payload = {
        "sub": user.guid,
        "exp": datetime.now(MOSCOW_TZ).replace(tzinfo=None) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:  # неверная подпись, истёк срок, мусор
        raise credentials_error

    user = await db.get(UserDatabase, payload.get("sub"))
    if user is None or user.role == "guest":  # пользователя нет в БД ИЛИ пользователь не подтвержден — доступа нет
        raise credentials_error

    return User.model_validate(user)

async def require_admin(user: UserDatabase = Depends(get_current_user)) -> UserDatabase:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user


async def require_token(token: str):
    if secrets.compare_digest(settings.system_token, token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")