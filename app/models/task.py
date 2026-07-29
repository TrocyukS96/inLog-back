from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

task_tag_links = Table(
    "task_tag_links",
    Base.metadata,
    Column("task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("task_tags.id", ondelete="CASCADE"), primary_key=True),
)


class TaskStatus(Base):
    __tablename__ = "task_statuses"
    __table_args__ = (UniqueConstraint("project_id", "name_en", name="uq_task_status_project_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ru: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped["Project"] = relationship("Project")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="status")


class TaskTag(Base):
    __tablename__ = "task_tags"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_task_tag_project_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_systemic: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_orphan: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    linked_object_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped["Project"] = relationship("Project")
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        secondary=task_tag_links,
        back_populates="tags",
    )


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("project_id", "slug", name="uq_task_project_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    creator_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status_id: Mapped[int] = mapped_column(
        ForeignKey("task_statuses.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    priority: Mapped[str] = mapped_column(String(20), default="medium", server_default="medium")
    status_position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    due_date_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped["Project"] = relationship("Project")
    creator: Mapped["User"] = relationship("User", foreign_keys=[creator_id])
    status: Mapped["TaskStatus"] = relationship("TaskStatus", back_populates="tasks")
    parent: Mapped["Task | None"] = relationship(
        "Task",
        back_populates="subtasks",
        remote_side="Task.id",
        foreign_keys=[parent_id],
    )
    tags: Mapped[list["TaskTag"]] = relationship(
        "TaskTag",
        secondary=task_tag_links,
        back_populates="tasks",
    )
    subtasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="parent",
        foreign_keys=[parent_id],
    )
