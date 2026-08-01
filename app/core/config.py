from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import urlparse


def parse_cors_origins(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return value
    return [origin.strip() for origin in value.split(",") if origin.strip()]


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

    secret_key: str = "change-me-in-production-use-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    email_verification_expire_hours: int = 24
    password_reset_expire_hours: int = 24
    email_change_expire_hours: int = 24

    frontend_url: str = "http://localhost:5173"
    email_from: str = "noreply@inlog.local"
    resend_api_key: str = ""

    super_admin_email: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_timeout: int = 10

    # Comma-separated origins, e.g. https://app.example.com,http://localhost:5173
    cors_origins: str = (
        "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return parse_cors_origins(self.cors_origins)

    @field_validator("smtp_password", mode="before")
    @classmethod
    def normalize_smtp_password(cls, value: str) -> str:
        if isinstance(value, str):
            return value.replace(" ", "")
        return value

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
