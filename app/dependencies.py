from datetime import datetime, timezone, timedelta
from pwdlib import PasswordHash
from app.backend.database.models import UserDatabase
from app.settings import settings
import jwt

password_hash = PasswordHash.recommended()

def create_access_token(user: UserDatabase) -> str:
    payload = {
        "sub": user.guid,
        "exp": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)