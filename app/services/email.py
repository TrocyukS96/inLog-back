import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_email(to_email: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        logger.info(
            "SMTP is not configured. Email to %s:\nSubject: %s\n\n%s",
            to_email,
            subject,
            body,
        )
        return

    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password or None,
        start_tls=settings.smtp_use_tls,
    )


async def send_verification_email(to_email: str, verification_url: str) -> None:
    subject = "Confirm your InLog account"
    body = (
        "Welcome to InLog!\n\n"
        "Please confirm your email address by opening the link below:\n"
        f"{verification_url}\n\n"
        "If you did not create an account, you can ignore this email."
    )
    await send_email(to_email, subject, body)


async def send_password_reset_email(to_email: str, reset_url: str) -> None:
    subject = "Reset your InLog password"
    body = (
        "You requested a password reset for your InLog account.\n\n"
        "Open the link below to set a new password:\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )
    await send_email(to_email, subject, body)


async def send_email_change_confirmation(to_email: str, confirmation_url: str) -> None:
    subject = "Confirm your new InLog email address"
    body = (
        "You requested to change the email address for your InLog account.\n\n"
        "Confirm the new email by opening the link below:\n"
        f"{confirmation_url}\n\n"
        "If you did not request this, you can ignore this email."
    )
    await send_email(to_email, subject, body)
