from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationUserRead(BaseModel):
    first_name: str = ""
    last_name: str = ""
    name: str = ""
    surname: str = ""
    email: str = ""
    avatar: str = ""


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    is_read: bool
    is_deleted: bool = False
    deleted: bool = False
    data: dict = Field(default_factory=dict)
    created_at: datetime
    sender: NotificationUserRead | None = None
    receiver: NotificationUserRead | None = None


class NotificationUpdate(BaseModel):
    is_read: bool | None = None
