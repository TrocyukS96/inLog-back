from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
DEFAULT_USER_SETTINGS: dict = {
    "language": "ru",
    "timezone": "Europe/Moscow",
    "sound_notification": True,
    "disabled_email_notifications": [],
    "disabled_inlog_notifications": [],
    "notifiable_days_of_week": [0, 1, 2, 3, 4, 5, 6],
    "notify_from_time": "09:00",
    "notify_to_time": "18:00",
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str | None] = mapped_column(String(150), nullable=True)

    name: Mapped[str] = mapped_column(String(150), default="", server_default="")
    patronymic: Mapped[str] = mapped_column(String(150), default="", server_default="")
    surname: Mapped[str] = mapped_column(String(150), default="", server_default="")
    company_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    position: Mapped[str] = mapped_column(String(255), default="", server_default="")
    about_myself: Mapped[str] = mapped_column(String(2000), default="", server_default="")
    role: Mapped[str] = mapped_column(String(50), default="member", server_default="member")
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    belonging: Mapped[str] = mapped_column(String(50), default="common", server_default="common")

    avatar: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    settings: Mapped[dict] = mapped_column(
        JSONB,
        default=lambda: DEFAULT_USER_SETTINGS.copy(),
    )

    receive_notifications: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    receive_advertisement: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    invitation_token: Mapped[str | None] = mapped_column(String(255), nullable=True)

    email_verification_tokens: Mapped[list["EmailVerificationToken"]] = relationship(
        "EmailVerificationToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        "PasswordResetToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    pending_email_changes: Mapped[list["PendingEmailChange"]] = relationship(
        "PendingEmailChange",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    @property
    def full_name(self) -> str:
        parts = [self.surname, self.name, self.patronymic]
        return " ".join(part for part in parts if part).strip()
