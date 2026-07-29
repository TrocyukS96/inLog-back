import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.uids import decode_uid, encode_uid
from app.models.pending_email_change import PendingEmailChange
from app.models.user import User
from app.services.auth import get_user_by_email
from app.services.email import send_email_change_confirmation


def build_email_change_url(user_id: int, token: str, new_email: str) -> str:
    uid = encode_uid(user_id)
    base = settings.frontend_url.rstrip("/")
    email_param = quote(new_email)
    return f"{base}/change-email?uid={uid}&token={token}&email={email_param}"


async def create_pending_email_change(
    db: AsyncSession,
    user: User,
    new_email: str,
) -> PendingEmailChange:
    await db.execute(
        delete(PendingEmailChange).where(PendingEmailChange.user_id == user.id)
    )

    token = secrets.token_urlsafe(32)
    pending_change = PendingEmailChange(
        user_id=user.id,
        new_email=new_email.lower(),
        token=token,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.email_change_expire_hours),
    )
    db.add(pending_change)
    await db.flush()
    return pending_change


async def get_pending_email_change(
    db: AsyncSession,
    *,
    user_id: int | None = None,
    token: str | None = None,
    new_email: str | None = None,
) -> PendingEmailChange | None:
    if token is None:
        return None

    query = (
        select(PendingEmailChange)
        .where(PendingEmailChange.token == token)
        .options(selectinload(PendingEmailChange.user))
    )
    if user_id is not None:
        query = query.where(PendingEmailChange.user_id == user_id)
    if new_email is not None:
        query = query.where(PendingEmailChange.new_email == new_email.lower())

    result = await db.execute(query)
    return result.scalar_one_or_none()


def _is_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at < datetime.now(UTC)


async def request_email_change(db: AsyncSession, user: User, new_email: str) -> None:
    normalized_email = new_email.lower()
    if normalized_email == user.email:
        raise ValueError("This email is already linked to your account.")

    existing_user = await get_user_by_email(db, normalized_email)
    if existing_user is not None:
        raise ValueError("A user with this email already exists.")

    pending_change = await create_pending_email_change(db, user, normalized_email)
    confirmation_url = build_email_change_url(user.id, pending_change.token, normalized_email)
    await send_email_change_confirmation(normalized_email, confirmation_url)


async def confirm_email_change(
    db: AsyncSession,
    *,
    email: str,
    uid: str,
    token: str,
) -> User:
    user_id = decode_uid(uid)
    pending_change = await get_pending_email_change(
        db,
        user_id=user_id,
        token=token,
        new_email=email,
    )
    if pending_change is None:
        raise ValueError("Invalid or expired email change link.")

    if _is_expired(pending_change.expires_at):
        raise ValueError("Email change link has expired.")

    user = pending_change.user
    if user is None:
        raise ValueError("User not found.")

    existing_user = await get_user_by_email(db, email)
    if existing_user is not None and existing_user.id != user.id:
        raise ValueError("A user with this email already exists.")

    user.email = email.lower()
    user.is_email_verified = True
    await db.execute(
        delete(PendingEmailChange).where(PendingEmailChange.user_id == user.id)
    )
    await db.flush()
    return user
