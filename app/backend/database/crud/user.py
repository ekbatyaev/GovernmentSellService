from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.backend.database.models import UserDatabase
from app.dependencies import verify_password, create_access_token
from sqlalchemy import select
from app.schemas.user import User, UpdateUser, FilterUser, LoginUser
from typing import Literal

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

async def update_user(db: AsyncSession, guid: str, updated_user: UpdateUser) -> Literal["not found", "updated"]:
    query = select(UserDatabase).where(UserDatabase.guid == guid)

    user = await db.scalar(query)

    if not user:
        return "not found"

    update_data = updated_user.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(user, field, value)

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        raise

    return "updated"

async def login_user(db: AsyncSession, email: str, password: str) -> LoginUser:
    result = await db.execute(select(UserDatabase).where(UserDatabase.email == email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password):
        return LoginUser(status="invalid")
    return LoginUser(status="updated", payload=create_access_token(user))
