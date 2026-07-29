from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.task import PaginatedTagsResponse, PaginatedTasksResponse, TaskStatusRead
from app.services.project import get_project
from app.services.task import list_task_statuses, list_task_tags, list_tasks, serialize_task_status

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])


async def _require_project(
    project_id: int,
    current_user: User,
    db: AsyncSession,
) -> None:
    project = await get_project(db, current_user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")


@router.get("/status/", response_model=list[TaskStatusRead])
async def get_task_statuses(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TaskStatusRead]:
    await _require_project(project_id, current_user, db)
    statuses = await list_task_statuses(db, project_id)
    return [serialize_task_status(status) for status in statuses]


@router.get("/tag/", response_model=PaginatedTagsResponse)
async def get_task_tags(
    project_id: int,
    request: Request,
    limit: int = Query(default=9999, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
    is_orphan: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedTagsResponse:
    await _require_project(project_id, current_user, db)
    base_path = str(request.url.replace(query="").path)
    return await list_task_tags(
        db,
        project_id,
        limit=limit,
        offset=offset,
        is_orphan=is_orphan,
        base_path=base_path,
    )


@router.get("/task/", response_model=PaginatedTasksResponse)
async def get_tasks(
    project_id: int,
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    is_template: bool = Query(default=False),
    status: int | None = Query(default=None),
    ordering: str | None = Query(default=None),
    name__icontains: str | None = Query(default=None),
    slug__icontains: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedTasksResponse:
    await _require_project(project_id, current_user, db)
    base_path = str(request.url.replace(query="").path)
    return await list_tasks(
        db,
        project_id,
        limit=limit,
        offset=offset,
        is_template=is_template,
        status_id=status,
        ordering=ordering,
        name_icontains=name__icontains,
        slug_icontains=slug__icontains,
        base_path=base_path,
    )
