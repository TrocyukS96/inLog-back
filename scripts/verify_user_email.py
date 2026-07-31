import asyncio
import sys

from sqlalchemy import delete, select

from app.db.session import async_session
from app.models.email_verification_token import EmailVerificationToken
from app.models.user import User


async def main() -> None:
    email = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lower()
    if not email:
        print("Usage: python scripts/verify_user_email.py <email>")
        return

    async with async_session() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

        if user is None:
            print(f"User not found: {email}")
            return

        user.is_email_verified = True
        await session.execute(
            delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
        )
        await session.commit()
        print(f"Email verified for user id={user.id} ({user.email})")


if __name__ == "__main__":
    asyncio.run(main())
