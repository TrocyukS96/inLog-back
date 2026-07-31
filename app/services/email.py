import logging
from email.message import EmailMessage

import aiosmtplib
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TEST_EMAIL_DOMAINS = frozenset({"example.com", "example.org", "test.com", "localhost"})


def _is_test_recipient(email: str) -> bool:
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[-1].lower()
    return domain in TEST_EMAIL_DOMAINS


def _log_email_fallback(to_email: str, subject: str, body: str) -> bool:
    logger.info(
        "Email provider is not configured. Email to %s:\nSubject: %s\n\n%s",
        to_email,
        subject,
        body,
    )
    return True


async def _send_via_resend(to_email: str, subject: str, body: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": settings.email_from,
                    "to": [to_email],
                    "subject": subject,
                    "text": body,
                },
            )
    except Exception:
        logger.exception("Failed to call Resend API for %s", to_email)
        return False

    if response.status_code >= 400:
        logger.error(
            "Resend API rejected email to %s (%s): %s",
            to_email,
            response.status_code,
            response.text,
        )
        return False

    return True


async def _send_via_smtp(to_email: str, subject: str, body: str) -> bool:
    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            start_tls=settings.smtp_use_tls,
            timeout=settings.smtp_timeout,
        )
    except Exception:
        logger.exception(
            "Failed to send email via SMTP to %s (subject: %s). Message body logged below.\n%s",
            to_email,
            subject,
            body,
        )
        return False

    return True


async def send_email(to_email: str, subject: str, body: str) -> bool:
    if _is_test_recipient(to_email):
        logger.info(
            "Skipped email for test recipient %s.\nSubject: %s\n\n%s",
            to_email,
            subject,
            body,
        )
        return True

    if settings.resend_api_key:
        return await _send_via_resend(to_email, subject, body)

    if settings.smtp_host:
        return await _send_via_smtp(to_email, subject, body)

    return _log_email_fallback(to_email, subject, body)


async def send_verification_email(to_email: str, verification_url: str) -> bool:
    subject = "Confirm your InLog account"
    body = (
        "Welcome to InLog!\n\n"
        "Please confirm your email address by opening the link below:\n"
        f"{verification_url}\n\n"
        "If you did not create an account, you can ignore this email."
    )
    return await send_email(to_email, subject, body)


async def send_password_reset_email(to_email: str, reset_url: str) -> bool:
    subject = "Reset your InLog password"
    body = (
        "You requested a password reset for your InLog account.\n\n"
        "Open the link below to set a new password:\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )
    return await send_email(to_email, subject, body)


async def send_email_change_confirmation(to_email: str, confirmation_url: str) -> bool:
    subject = "Confirm your new InLog email address"
    body = (
        "You requested to change the email address for your InLog account.\n\n"
        "Confirm the new email by opening the link below:\n"
        f"{confirmation_url}\n\n"
        "If you did not request this, you can ignore this email."
    )
    return await send_email(to_email, subject, body)
