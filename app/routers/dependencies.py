from fastapi import Security
from fastapi.security import APIKeyHeader
from app.settings import settings
import secrets
from fastapi import status
from fastapi.exceptions import HTTPException

_token_header = APIKeyHeader(name="X-Token")

async def require_token(token: str = Security(_token_header)):
    if secrets.compare_digest(settings.system_token, token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")