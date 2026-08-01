from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_access_payload, require_permission, require_super_admin
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin import (
    AdminAccessRead,
    AdminUserRead,
    AdminUserRoleUpdate,
    PaginatedAdminOrganizationsResponse,
    PaginatedAdminProjectsResponse,
    PaginatedAdminTasksResponse,
    PaginatedAdminTaskStatusesResponse,
    PaginatedAdminTaskTagsResponse,
    PaginatedAdminUsersResponse,
)
from app.services.admin.catalog import (
    list_all_organizations,
    list_all_projects,
    list_all_task_statuses,
    list_all_task_tags,
    list_all_tasks,
)
from app.services.admin.users import delete_user_by_admin, list_all_users, update_user_platform_role

router = APIRouter(prefix="/admin", tags=["admin"])


def _admin_base_path(request: Request, resource: str) -> str:
    return str(request.url.replace(path=f"/api/admin/{resource}/", query=""))


@router.get("/access/", response_model=AdminAccessRead)
async def get_admin_access(
    current_user: User = Depends(require_permission(Permission.ACCESS_ADMIN_PANEL)),
) -> AdminAccessRead:
    return AdminAccessRead(**get_admin_access_payload(current_user))


@router.get("/user/", response_model=PaginatedAdminUsersResponse)
async def admin_list_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_ALL_USERS)),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
) -> PaginatedAdminUsersResponse:
    return await list_all_users(
        db,
        limit=limit,
        offset=offset,
        search=search,
        base_path=_admin_base_path(request, "user"),
    )


@router.delete("/user/{user_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DELETE_USERS)),
) -> None:
    try:
        await delete_user_by_admin(db, current_user, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/user/{user_id}/role/", response_model=AdminUserRead)
async def admin_update_user_role(
    user_id: int,
    data: AdminUserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
) -> AdminUserRead:
    try:
        return await update_user_platform_role(db, current_user, user_id, data.role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/organization/", response_model=PaginatedAdminOrganizationsResponse)
async def admin_list_organizations(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_ALL_ORGANIZATIONS)),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
) -> PaginatedAdminOrganizationsResponse:
    return await list_all_organizations(
        db,
        limit=limit,
        offset=offset,
        search=search,
        base_path=_admin_base_path(request, "organization"),
    )


@router.get("/project/", response_model=PaginatedAdminProjectsResponse)
async def admin_list_projects(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_ALL_PROJECTS)),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    organization: int | None = Query(default=None),
) -> PaginatedAdminProjectsResponse:
    return await list_all_projects(
        db,
        limit=limit,
        offset=offset,
        search=search,
        organization_id=organization,
        base_path=_admin_base_path(request, "project"),
    )


@router.get("/task/", response_model=PaginatedAdminTasksResponse)
async def admin_list_tasks(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_ALL_TASKS)),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    project: int | None = Query(default=None),
) -> PaginatedAdminTasksResponse:
    return await list_all_tasks(
        db,
        limit=limit,
        offset=offset,
        search=search,
        project_id=project,
        base_path=_admin_base_path(request, "task"),
    )


@router.get("/task-status/", response_model=PaginatedAdminTaskStatusesResponse)
async def admin_list_task_statuses(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_ALL_TASK_STATUSES)),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    project: int | None = Query(default=None),
) -> PaginatedAdminTaskStatusesResponse:
    return await list_all_task_statuses(
        db,
        limit=limit,
        offset=offset,
        project_id=project,
        base_path=_admin_base_path(request, "task-status"),
    )


@router.get("/task-tag/", response_model=PaginatedAdminTaskTagsResponse)
async def admin_list_task_tags(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_ALL_TASK_TAGS)),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    project: int | None = Query(default=None),
) -> PaginatedAdminTaskTagsResponse:
    return await list_all_task_tags(
        db,
        limit=limit,
        offset=offset,
        search=search,
        project_id=project,
        base_path=_admin_base_path(request, "task-tag"),
    )
