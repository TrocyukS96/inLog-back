from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import urlparse


def normalize_database_url(url: str) -> str:
    """Convert standard postgres URL to async SQLAlchemy format."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "inLog API"
    app_version: str = "0.1.0"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/inlog"

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @property
    def db_connect_args(self) -> dict:
        parsed = urlparse(self.database_url)
        host = parsed.hostname or ""

        connect_args: dict = {}

        if "supabase.co" in host or "supabase.com" in host or "render.com" in host:
            connect_args["ssl"] = "require"

        # Supabase transaction pooler (port 6543) requires disabling prepared statements
        if parsed.port == 6543:
            connect_args["statement_cache_size"] = 0

        return connect_args


settings = Settings()
