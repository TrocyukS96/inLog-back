from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

INVITATION_PENDING = "pending"
INVITATION_ACCEPTED = "accepted"
INVITATION_REJECTED = "rejected"


class ProjectUserInvitation(Base):
    __tablename__ = "project_user_invitations"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "invitee_id",
            "status",
            name="uq_project_invitation_pending",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    inviter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    invitee_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(50), default="member", server_default="member")
    status: Mapped[str] = mapped_column(
        String(20),
        default=INVITATION_PENDING,
        server_default=INVITATION_PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped["Project"] = relationship("Project")
    inviter: Mapped["User"] = relationship("User", foreign_keys=[inviter_id])
    invitee: Mapped["User"] = relationship("User", foreign_keys=[invitee_id])
