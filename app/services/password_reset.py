import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import hash_password
from app.core.uids import decode_uid, encode_uid
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services.email import send_password_reset_email


def build_password_reset_url(user_id: int, token: str) -> str:
    uid = encode_uid(user_id)
    base = settings.frontend_url.rstrip("/")
    return f"{base}/recover?uid={uid}&token={token}"


async def create_password_reset_token(db: AsyncSession, user: User) -> PasswordResetToken:
    await db.execute(
        delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    )

    token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.password_reset_expire_hours),
    )
    db.add(reset_token)
    await db.flush()
    return reset_token


async def get_password_reset_token(
    db: AsyncSession,
    *,
    user_id: int | None = None,
    token: str | None = None,
) -> PasswordResetToken | None:
    if token is None:
        return None

    query = (
        select(PasswordResetToken)
        .where(PasswordResetToken.token == token)
        .options(selectinload(PasswordResetToken.user))
    )
    if user_id is not None:
        query = query.where(PasswordResetToken.user_id == user_id)

    result = await db.execute(query)
    return result.scalar_one_or_none()


def _is_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at < datetime.now(UTC)


async def request_password_reset(db: AsyncSession, email: str) -> str:
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()

    if user is None:
        return "If an account with this email exists, a password reset email has been sent."

    reset_token = await create_password_reset_token(db, user)
    reset_url = build_password_reset_url(user.id, reset_token.token)
    await send_password_reset_email(user.email, reset_url)
    return "If an account with this email exists, a password reset email has been sent."


async def confirm_password_reset(
    db: AsyncSession,
    *,
    uid: str,
    token: str,
    new_password1: str,
    new_password2: str,
) -> None:
    if new_password1 != new_password2:
        raise ValueError("Passwords do not match.")

    user_id = decode_uid(uid)
    reset_token = await get_password_reset_token(db, user_id=user_id, token=token)
    if reset_token is None:
        raise ValueError("Invalid or expired password reset link.")

    if _is_expired(reset_token.expires_at):
        raise ValueError("Password reset link has expired.")

    user = reset_token.user
    if user is None:
        raise ValueError("User not found.")

    user.hashed_password = hash_password(new_password1)
    await db.execute(
        delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    )
    await db.flush()
