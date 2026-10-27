from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.backend.database.models import UserDatabase
from sqlalchemy import select
from app.schemas.user import User, FilterUser

async def put_user(db: AsyncSession, user: User) -> UserDatabase:
    new_user = UserDatabase(**user.model_dump())
    db.add(new_user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise
    await db.refresh(new_user)
    return new_user

async def search_users(db: AsyncSession, filters: FilterUser) -> list[User]:
    query = select(UserDatabase)

    if filters.email:
        query = query.where(UserDatabase.email == filters.email)

    if filters.role:
        query = query.where(UserDatabase.role == filters.role)

    if filters.created_at_from:
        query = query.where(UserDatabase.created_at >= filters.created_at_from)

    if filters.created_at_to:
        query = query.where(UserDatabase.created_at <= filters.created_at_to)

    query = query.order_by(UserDatabase.email.asc())

    result = await db.execute(query)
    users = result.scalars().all()
    data = [User.model_validate(n) for n in users]
    return data

async def get_user(db: AsyncSession, guid: str) -> User | None:
    user = await db.get(UserDatabase, guid)
    return user

async def delete_user(db: AsyncSession, guid: str) -> bool:
    user = await db.get(UserDatabase, guid)
    if not user:
        return False
    await db.delete(user)
    await db.commit()
    return True