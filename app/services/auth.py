from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import DEFAULT_USER_SETTINGS, User
from app.schemas.auth import LoginRequest, RegistrationRequest


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, data: RegistrationRequest) -> User:
    user = User(
        email=data.email.lower(),
        hashed_password=hash_password(data.password1),
        username=data.username,
        belonging=data.belonging,
        receive_notifications=data.receive_notifications,
        receive_advertisement=data.receive_advertisement,
        invitation_token=data.invitation_token or None,
        settings=DEFAULT_USER_SETTINGS.copy(),
        avatar={},
        is_email_verified=False,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, data: LoginRequest) -> User | None:
    user = await get_user_by_email(db, data.email)
    if user is None or not verify_password(data.password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    if not user.is_email_verified:
        return None
    return user


def create_tokens_for_user(user: User) -> tuple[str, str]:
    return create_access_token(user.id), create_refresh_token(user.id)
