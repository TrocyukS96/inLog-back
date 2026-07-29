from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    receiver_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    sender_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    data: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    receiver: Mapped["User"] = relationship("User", foreign_keys=[receiver_id])
    sender: Mapped["User | None"] = relationship("User", foreign_keys=[sender_id])
