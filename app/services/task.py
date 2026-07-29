import re
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.task import Task, TaskStatus, TaskTag
from app.models.user import User
from app.schemas.task import (
    PaginatedTagsResponse,
    PaginatedTasksResponse,
    TaskCreate,
    TaskEquipmentRead,
    TaskRead,
    TaskStatusRead,
    TaskTagRead,
    TaskUpdate,
)
from app.services.user import serialize_user

DEFAULT_STATUSES: list[dict[str, str | int]] = [
    {"name_en": "No status", "name_ru": "Без статуса", "position": 0},
    {"name_en": "In progress", "name_ru": "В работе", "position": 1},
    {"name_en": "Closed", "name_ru": "Закрыто", "position": 2},
]


def generate_task_slug(name: str) -> str:
    base = re.sub(r"[^\w\s-]", "", name.lower(), flags=re.UNICODE)
    base = re.sub(r"[\s_-]+", "-", base).strip("-")
    if not base:
        base = "task"
    return f"{base}-{uuid.uuid4().hex[:8]}"


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _task_load_options():
    return (
        selectinload(Task.creator),
        selectinload(Task.status),
        selectinload(Task.tags),
        selectinload(Task.subtasks).selectinload(Task.creator),
        selectinload(Task.subtasks).selectinload(Task.status),
        selectinload(Task.subtasks).selectinload(Task.tags),
    )


async def _get_task_status_for_project(
    db: AsyncSession,
    project_id: int,
    status_id: int | None,
) -> TaskStatus:
    if status_id is None:
        return await get_default_status(db, project_id)

    result = await db.execute(
        select(TaskStatus).where(
            TaskStatus.id == status_id,
            TaskStatus.project_id == project_id,
        )
    )
    status = result.scalar_one_or_none()
    if status is None:
        raise ValueError("status_not_found")
    return status


async def _next_status_position(
    db: AsyncSession,
    project_id: int,
    status_id: int,
    parent_id: int | None,
) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(Task.status_position), 0)).where(
            Task.project_id == project_id,
            Task.status_id == status_id,
            Task.parent_id.is_(parent_id) if parent_id is None else Task.parent_id == parent_id,
        )
    )
    return int(result.scalar_one()) + 1


async def get_task_by_slug(db: AsyncSession, project_id: int, slug: str) -> Task | None:
    result = await db.execute(
        select(Task)
        .where(Task.project_id == project_id, Task.slug == slug)
        .options(*_task_load_options())
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def create_task(
    db: AsyncSession,
    project_id: int,
    creator: User,
    data: TaskCreate,
) -> Task:
    status = await _get_task_status_for_project(db, project_id, data.status)

    parent_id = data.parent
    if parent_id is not None:
        parent_result = await db.execute(
            select(Task.id).where(
                Task.id == parent_id,
                Task.project_id == project_id,
            )
        )
        if parent_result.scalar_one_or_none() is None:
            raise ValueError("parent_not_found")

    status_position = await _next_status_position(db, project_id, status.id, parent_id)

    task = Task(
        project_id=project_id,
        creator_id=creator.id,
        status_id=status.id,
        parent_id=parent_id,
        name=data.name.strip(),
        slug=generate_task_slug(data.name),
        description=data.description or "",
        priority=data.priority or "medium",
        status_position=status_position,
        due_date_start=_parse_datetime(data.due_date_start),
        due_date_end=_parse_datetime(data.due_date_end),
        is_template=data.is_template,
    )
    db.add(task)
    await db.flush()

    loaded = await get_task_by_slug(db, project_id, task.slug)
    assert loaded is not None
    return loaded


async def update_task(
    db: AsyncSession,
    task: Task,
    data: TaskUpdate,
) -> Task:
    updates = data.model_dump(exclude_unset=True, exclude={"id", "tags"})

    if "status" in updates:
        status = await _get_task_status_for_project(db, task.project_id, updates.pop("status"))
        task.status_id = status.id

    if "parent" in updates:
        parent_id = updates.pop("parent")
        if parent_id is not None:
            parent_result = await db.execute(
                select(Task.id).where(
                    Task.id == parent_id,
                    Task.project_id == task.project_id,
                )
            )
            if parent_result.scalar_one_or_none() is None:
                raise ValueError("parent_not_found")
        task.parent_id = parent_id

    for date_field in ("due_date_start", "due_date_end"):
        if date_field in updates:
            updates[date_field] = _parse_datetime(updates[date_field])

    for field, value in updates.items():
        if hasattr(task, field):
            setattr(task, field, value)

    if data.tags is not None:
        if data.tags:
            tags_result = await db.execute(
                select(TaskTag).where(
                    TaskTag.id.in_(data.tags),
                    TaskTag.project_id == task.project_id,
                )
            )
            task.tags = list(tags_result.scalars().all())
        else:
            task.tags = []

    await db.flush()

    loaded = await get_task_by_slug(db, task.project_id, task.slug)
    assert loaded is not None
    return loaded


async def delete_task(db: AsyncSession, task: Task) -> None:
    subtasks_result = await db.execute(select(Task).where(Task.parent_id == task.id))
    for subtask in subtasks_result.scalars().all():
        await delete_task(db, subtask)
    await db.delete(task)
    await db.flush()


def serialize_task_status(status: TaskStatus) -> TaskStatusRead:
    return TaskStatusRead(
        id=status.id,
        name_en=status.name_en,
        name_ru=status.name_ru,
        position=status.position,
        project=status.project_id,
    )


def serialize_task_tag(tag: TaskTag) -> TaskTagRead:
    return TaskTagRead(
        id=tag.id,
        name=tag.name,
        project=tag.project_id,
        is_systemic=tag.is_systemic,
        is_orphan=tag.is_orphan,
        linked_object_content_type=tag.linked_object_content_type,
    )


def serialize_task(task: Task, *, include_subtasks: bool = True) -> TaskRead:
    subtasks: list[TaskRead] = []
    if include_subtasks and task.subtasks:
        subtasks = [serialize_task(subtask, include_subtasks=False) for subtask in task.subtasks]

    return TaskRead(
        id=task.id,
        name=task.name,
        description=task.description or "",
        slug=task.slug,
        project=task.project_id,
        creator=serialize_user(task.creator),
        priority=task.priority,
        status=serialize_task_status(task.status),
        status_position=task.status_position,
        due_date_start=_format_datetime(task.due_date_start),
        due_date_end=_format_datetime(task.due_date_end),
        tags=[serialize_task_tag(tag) for tag in task.tags],
        equipment=TaskEquipmentRead(project=task.project_id),
        parent=task.parent_id,
        archived=task.archived,
        subtasks=subtasks,
        doers=[],
        supervisor=None,
        files=[],
        created_at=task.created_at,
        is_template=task.is_template,
        comments=[],
    )


async def ensure_default_statuses(db: AsyncSession, project_id: int) -> list[TaskStatus]:
    result = await db.execute(
        select(TaskStatus)
        .where(TaskStatus.project_id == project_id)
        .order_by(TaskStatus.position.asc(), TaskStatus.id.asc())
    )
    statuses = list(result.scalars().all())
    if statuses:
        return statuses

    for item in DEFAULT_STATUSES:
        db.add(
            TaskStatus(
                project_id=project_id,
                name_en=str(item["name_en"]),
                name_ru=str(item["name_ru"]),
                position=int(item["position"]),
            )
        )
    await db.flush()

    result = await db.execute(
        select(TaskStatus)
        .where(TaskStatus.project_id == project_id)
        .order_by(TaskStatus.position.asc(), TaskStatus.id.asc())
    )
    return list(result.scalars().all())


async def get_default_status(db: AsyncSession, project_id: int) -> TaskStatus:
    statuses = await ensure_default_statuses(db, project_id)
    return statuses[0]


async def list_task_statuses(db: AsyncSession, project_id: int) -> list[TaskStatus]:
    return await ensure_default_statuses(db, project_id)


def _build_page_urls(
    *,
    base_path: str,
    limit: int,
    offset: int,
    total: int,
    query_suffix: str = "",
) -> tuple[str | None, str | None]:
    next_url = None
    previous_url = None
    suffix = f"{query_suffix}&" if query_suffix else ""

    if offset + limit < total:
        next_url = f"{base_path}?{suffix}limit={limit}&offset={offset + limit}"
    if offset > 0:
        previous_offset = max(offset - limit, 0)
        previous_url = f"{base_path}?{suffix}limit={limit}&offset={previous_offset}"

    return next_url, previous_url


async def list_task_tags(
    db: AsyncSession,
    project_id: int,
    *,
    limit: int = 9999,
    offset: int = 0,
    is_orphan: bool | None = None,
    base_path: str,
) -> PaginatedTagsResponse:
    query = select(TaskTag).where(TaskTag.project_id == project_id)
    if is_orphan is not None:
        query = query.where(TaskTag.is_orphan.is_(is_orphan))

    count_query = select(func.count()).select_from(query.subquery())
    total = int((await db.execute(count_query)).scalar_one())

    result = await db.execute(
        query.order_by(TaskTag.name.asc()).limit(limit).offset(offset)
    )
    tags = list(result.scalars().all())

    query_suffix = ""
    if is_orphan is not None:
        query_suffix = f"is_orphan={'true' if is_orphan else 'false'}"

    next_url, previous_url = _build_page_urls(
        base_path=base_path,
        limit=limit,
        offset=offset,
        total=total,
        query_suffix=query_suffix,
    )

    return PaginatedTagsResponse(
        count=total,
        next=next_url,
        previous=previous_url,
        results=[serialize_task_tag(tag) for tag in tags],
    )


async def list_tasks(
    db: AsyncSession,
    project_id: int,
    *,
    limit: int = 100,
    offset: int = 0,
    is_template: bool | None = None,
    status_id: int | None = None,
    parent_isnull: bool | None = None,
    ordering: str | None = None,
    name_icontains: str | None = None,
    slug_icontains: str | None = None,
    base_path: str,
) -> PaginatedTasksResponse:
    await ensure_default_statuses(db, project_id)

    filters = [Task.project_id == project_id]
    if is_template is not None:
        filters.append(Task.is_template.is_(is_template))
    if status_id is not None:
        filters.append(Task.status_id == status_id)
    if parent_isnull is True:
        filters.append(Task.parent_id.is_(None))
    elif parent_isnull is False:
        filters.append(Task.parent_id.is_not(None))
    if name_icontains:
        filters.append(Task.name.ilike(f"%{name_icontains}%"))
    if slug_icontains:
        filters.append(Task.slug.ilike(f"%{slug_icontains}%"))

    count_result = await db.execute(select(func.count()).select_from(Task).where(*filters))
    total = int(count_result.scalar_one())

    query = (
        select(Task)
        .where(*filters)
        .options(
            selectinload(Task.creator),
            selectinload(Task.status),
            selectinload(Task.tags),
        )
    )

    order_column = Task.status_position.asc()
    if ordering:
        descending = ordering.startswith("-")
        field_name = ordering.lstrip("-")
        column = getattr(Task, field_name, None)
        if column is not None:
            order_column = column.desc() if descending else column.asc()

    result = await db.execute(query.order_by(order_column, Task.id.asc()).limit(limit).offset(offset))
    tasks = list(result.scalars().unique().all())

    query_parts: list[str] = []
    if is_template is not None:
        query_parts.append(f"is_template={'true' if is_template else 'false'}")
    if status_id is not None:
        query_parts.append(f"status={status_id}")
    if parent_isnull is not None:
        query_parts.append(f"parent__isnull={'true' if parent_isnull else 'false'}")
    if name_icontains:
        query_parts.append(f"name__icontains={name_icontains}")
    if slug_icontains:
        query_parts.append(f"slug__icontains={slug_icontains}")
    if ordering:
        query_parts.append(f"ordering={ordering}")

    next_url, previous_url = _build_page_urls(
        base_path=base_path,
        limit=limit,
        offset=offset,
        total=total,
        query_suffix="&".join(query_parts),
    )

    return PaginatedTasksResponse(
        count=total,
        next=next_url,
        previous=previous_url,
        results=[serialize_task(task, include_subtasks=False) for task in tasks],
    )
