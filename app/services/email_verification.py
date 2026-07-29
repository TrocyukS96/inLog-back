import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.uids import decode_uid, encode_uid
from app.models.email_verification_token import EmailVerificationToken
from app.models.user import User
from app.services.email import send_verification_email


def build_verification_url(user_id: int, token: str) -> str:
    uid = encode_uid(user_id)
    base = settings.frontend_url.rstrip("/")
    return f"{base}/email-confirmation?uid={uid}&key={token}"


async def create_verification_token(db: AsyncSession, user: User) -> EmailVerificationToken:
    await db.execute(
        delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )

    token = secrets.token_urlsafe(32)
    verification_token = EmailVerificationToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.email_verification_expire_hours),
    )
    db.add(verification_token)
    await db.flush()
    return verification_token


async def send_user_verification_email(db: AsyncSession, user: User) -> None:
    verification_token = await create_verification_token(db, user)
    verification_url = build_verification_url(user.id, verification_token.token)
    await send_verification_email(user.email, verification_url)


async def get_verification_token(
    db: AsyncSession,
    *,
    user_id: int | None = None,
    token: str | None = None,
) -> EmailVerificationToken | None:
    if token is None:
        return None

    query = (
        select(EmailVerificationToken)
        .where(EmailVerificationToken.token == token)
        .options(selectinload(EmailVerificationToken.user))
    )
    if user_id is not None:
        query = query.where(EmailVerificationToken.user_id == user_id)

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def verify_user_email(
    db: AsyncSession,
    *,
    key: str,
    uid: str | None = None,
) -> User:
    user_id = decode_uid(uid) if uid else None

    verification_token = await get_verification_token(db, user_id=user_id, token=key)
    if verification_token is None:
        raise ValueError("Invalid verification link.")

    expires_at = verification_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < datetime.now(UTC):
        raise ValueError("Verification link has expired.")

    user = verification_token.user
    if user is None:
        raise ValueError("User not found.")

    user.is_email_verified = True
    await db.execute(
        delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    await db.flush()
    return user


async def resend_verification_email(db: AsyncSession, email: str) -> str:
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()

    if user is None:
        return "If an account with this email exists, a verification email has been sent."

    if user.is_email_verified:
        return "Email is already verified."

    await send_user_verification_email(db, user)
    return "Verification email has been sent."
