import asyncio
import sys

from sqlalchemy import select

from app.core.roles import PlatformRole, normalize_platform_role
from app.db.session import async_session
from app.models.user import User


async def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python scripts/set_platform_role.py <email> <member|admin|super_admin>")
        return

    email = sys.argv[1].strip().lower()
    role_value = sys.argv[2].strip().lower()

    try:
        role = PlatformRole(role_value)
    except ValueError:
        allowed = ", ".join(item.value for item in PlatformRole)
        print(f"Invalid role. Allowed values: {allowed}")
        return

    async with async_session() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if user is None:
            print(f"User not found: {email}")
            return

        previous_role = normalize_platform_role(user.role)
        user.role = role.value
        await session.commit()
        print(f"Updated user id={user.id} ({email}): {previous_role} -> {role.value}")


if __name__ == "__main__":
    asyncio.run(main())
