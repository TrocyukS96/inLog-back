import asyncio

from sqlalchemy import text

from app.db.session import engine


async def main() -> None:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        print("OK", result.scalar())


asyncio.run(main())
