from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.settings import settings

DATABASE_URL = (
    f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
)

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

Session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)

Base = declarative_base()


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_db() -> None:
    await engine.dispose()

async def get_db() -> AsyncIterator[AsyncSession]:
    async with Session() as db:
        yield db

@asynccontextmanager
async def db_session() -> AsyncIterator[AsyncSession]:
    async with Session() as db:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise

@asynccontextmanager
async def advisory_lock(lock_key: int) -> AsyncIterator[bool]:
    """
    Пытается взять advisory-лок и гарантированно снимает его на ТОМ ЖЕ соединении.

        async with advisory_lock(42) as acquired:
            if not acquired:
                return
            ...

    Соединение держится всё время жизни блока: advisory-лок привязан к соединению,
    поэтому брать и снимать его через разные сессии нельзя.
    """
    async with engine.connect() as conn:
        acquired = bool(
            (await conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": lock_key})).scalar()
        )
        try:
            yield acquired
        finally:
            if acquired:
                await conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key})

async def advisory_unlock(conn: AsyncConnection | AsyncSession, lock_key: int) -> bool:
    return bool(
        (await conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key})).scalar()
    )