import asyncio
import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.uids import encode_uid
from app.db.session import async_session
from app.models.email_verification_token import EmailVerificationToken
from app.models.user import User


async def main() -> None:
    email = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lower()
    if not email:
        print("Usage: python scripts/check_user.py <email>")
        return

    async with async_session() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

        if user is None:
            print(f"USER: not found for {email}")
            return

        print(f"USER id={user.id}")
        print(f"  email={user.email}")
        print(f"  is_active={user.is_active}")
        print(f"  is_email_verified={user.is_email_verified}")
        print(f"  created_at={user.created_at}")

        token = (
            await session.execute(
                select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
            )
        ).scalar_one_or_none()

        if token is None:
            print("  verification_token: none")
            return

        uid = encode_uid(user.id)
        base = settings.frontend_url.rstrip("/")
        url = f"{base}/email-confirmation?uid={uid}&key={token.token}"
        print(f"  verification_token: exists, expires={token.expires_at}")
        print(f"  confirmation_url: {url}")


if __name__ == "__main__":
    asyncio.run(main())
