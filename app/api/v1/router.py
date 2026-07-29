from sqlalchemy import text

from fastapi import APIRouter

from app.core.config import settings
from app.db.session import engine

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    result: dict[str, str] = {"status": "ok", "database": "ok"}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        result["database"] = "error"
        if settings.debug:
            result["database_error"] = str(exc)

    return result
