from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.task import (
    PaginatedTagsResponse,
    PaginatedTasksResponse,
    TaskCreate,
    TaskRead,
    TaskStatusRead,
    TaskUpdate,
)
from app.services.project import get_project
from app.services.task import (
    create_task,
    delete_task,
    get_task_by_slug,
    list_task_statuses,
    list_task_tags,
    list_tasks,
    serialize_task,
    serialize_task_status,
    update_task,
)

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])


async def _require_project(
    project_id: int,
    current_user: User,
    db: AsyncSession,
) -> None:
    project = await get_project(db, current_user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")


async def _get_task_or_404(db: AsyncSession, project_id: int, task_slug: str):
    task = await get_task_by_slug(db, project_id, task_slug)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return task


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


@router.post("/task/", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def add_task(
    project_id: int,
    data: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    await _require_project(project_id, current_user, db)
    try:
        task = await create_task(db, project_id, current_user, data)
    except ValueError as exc:
        error_code = str(exc)
        if error_code == "status_not_found":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Status not found.",
            ) from exc
        if error_code == "parent_not_found":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent task not found.",
            ) from exc
        raise
    return serialize_task(task)


@router.get("/task/{task_slug}/", response_model=TaskRead)
async def get_task(
    project_id: int,
    task_slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    await _require_project(project_id, current_user, db)
    task = await _get_task_or_404(db, project_id, task_slug)
    return serialize_task(task)


@router.patch("/task/{task_slug}/", response_model=TaskRead)
async def patch_task(
    project_id: int,
    task_slug: str,
    data: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    await _require_project(project_id, current_user, db)
    task = await _get_task_or_404(db, project_id, task_slug)
    try:
        updated = await update_task(db, task, data)
    except ValueError as exc:
        error_code = str(exc)
        if error_code in {"status_not_found", "parent_not_found"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid task reference.",
            ) from exc
        raise
    return serialize_task(updated)


@router.delete("/task/{task_slug}/", status_code=status.HTTP_204_NO_CONTENT)
async def remove_task(
    project_id: int,
    task_slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _require_project(project_id, current_user, db)
    task = await _get_task_or_404(db, project_id, task_slug)
    await delete_task(db, task)
