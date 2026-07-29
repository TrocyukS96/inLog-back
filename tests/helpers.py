from sqlalchemy import select

from app.core.uids import encode_uid
from app.db.session import async_session
from app.models.email_verification_token import EmailVerificationToken
from app.models.password_reset_token import PasswordResetToken
from app.models.pending_email_change import PendingEmailChange
from app.models.user import User


async def get_verification_credentials(email: str) -> tuple[str, str]:
    async with async_session() as session:
        user_result = await session.execute(select(User).where(User.email == email.lower()))
        user = user_result.scalar_one()

        token_result = await session.execute(
            select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
        )
        verification_token = token_result.scalar_one()

        return encode_uid(user.id), verification_token.token


async def get_password_reset_credentials(email: str) -> tuple[str, str]:
    async with async_session() as session:
        user_result = await session.execute(select(User).where(User.email == email.lower()))
        user = user_result.scalar_one()

        token_result = await session.execute(
            select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
        )
        reset_token = token_result.scalar_one()

        return encode_uid(user.id), reset_token.token


async def get_email_change_credentials(user_id: int) -> tuple[str, str, str]:
    async with async_session() as session:
        token_result = await session.execute(
            select(PendingEmailChange).where(PendingEmailChange.user_id == user_id)
        )
        pending_change = token_result.scalar_one()

        return encode_uid(user_id), pending_change.token, pending_change.new_email
