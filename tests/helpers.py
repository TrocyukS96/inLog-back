from sqlalchemy import select

from app.core.uids import encode_uid
from app.db.session import async_session
from app.models.email_verification_token import EmailVerificationToken
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
