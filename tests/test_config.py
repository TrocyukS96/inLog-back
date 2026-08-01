import os

from app.core.config import Settings, merge_cors_origins, parse_cors_origins


def test_cors_origins_from_comma_separated_env(monkeypatch) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "https://in-log-livid.vercel.app,http://localhost:5173",
    )
    settings = Settings()
    assert settings.cors_origins_list == merge_cors_origins(
        [
            "https://in-log-livid.vercel.app",
            "http://localhost:5173",
        ]
    )


def test_parse_cors_origins_strips_whitespace() -> None:
    assert parse_cors_origins(" https://a.com , https://b.com ") == [
        "https://a.com",
        "https://b.com",
    ]
