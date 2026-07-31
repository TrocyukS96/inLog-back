import aiosmtplib
import pytest

from app.services.email import TEST_EMAIL_DOMAINS, _is_test_recipient, send_email


@pytest.mark.asyncio
async def test_send_email_skips_test_domains(monkeypatch) -> None:
    called = False

    async def fake_smtp_send(*args, **kwargs) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr("app.services.email.aiosmtplib.send", fake_smtp_send)
    monkeypatch.setattr("app.services.email.settings.smtp_host", "smtp.gmail.com")

    await send_email("user@example.com", "Subject", "Body")

    assert called is False
    assert _is_test_recipient("notif-6a1e4b36@example.com") is True


@pytest.mark.asyncio
async def test_send_email_uses_smtp_for_real_domains(monkeypatch) -> None:
    called = False

    async def fake_smtp_send(*args, **kwargs) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr("app.services.email.aiosmtplib.send", fake_smtp_send)
    monkeypatch.setattr("app.services.email.settings.smtp_host", "smtp.gmail.com")
    monkeypatch.setattr("app.services.email.settings.email_from", "noreply@test.local")

    result = await send_email("user@gmail.com", "Subject", "Body")

    assert called is True
    assert result is True


@pytest.mark.asyncio
async def test_send_email_returns_false_on_smtp_failure(monkeypatch) -> None:
    async def failing_smtp_send(*args, **kwargs) -> None:
        raise aiosmtplib.errors.SMTPConnectTimeoutError("timeout")

    monkeypatch.setattr("app.services.email.aiosmtplib.send", failing_smtp_send)
    monkeypatch.setattr("app.services.email.settings.smtp_host", "smtp.gmail.com")

    result = await send_email("user@gmail.com", "Subject", "Body with link")

    assert result is False


def test_test_email_domains_include_example_com() -> None:
    assert "example.com" in TEST_EMAIL_DOMAINS
