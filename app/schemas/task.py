from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserRead


class TaskStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name_en: str
    name_ru: str
    position: int
    project: int | None = None


class TaskTagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    project: int | None = None
    is_systemic: bool = False
    is_orphan: bool = False
    linked_object_content_type: str | None = None


class PaginatedTagsResponse(BaseModel):
    count: int
    next: str | None
    previous: str | None
    results: list[TaskTagRead]


class TaskEquipmentRead(BaseModel):
    id: int | None = None
    name: str = ""
    project: int | None = None
    created_at: str | None = None


class TaskDoerRead(BaseModel):
    id: int
    user: UserRead | None = None


class TaskSupervisorRead(BaseModel):
    id: int | None = None
    user: UserRead | None = None
    project: int | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str = ""
    slug: str
    project: int
    creator: UserRead
    priority: str
    status: TaskStatusRead
    status_position: int | str = 0
    due_date_start: str = ""
    due_date_end: str = ""
    tags: list[TaskTagRead] = Field(default_factory=list)
    equipment: TaskEquipmentRead = Field(default_factory=TaskEquipmentRead)
    parent: int | None = None
    archived: bool = False
    subtasks: list["TaskRead"] = Field(default_factory=list)
    doers: list[TaskDoerRead] = Field(default_factory=list)
    supervisor: TaskSupervisorRead | None = None
    files: list[dict] = Field(default_factory=list)
    created_at: datetime
    is_template: bool = False
    comments: list[dict] = Field(default_factory=list)


class PaginatedTasksResponse(BaseModel):
    count: int
    next: str | None
    previous: str | None
    results: list[TaskRead]
