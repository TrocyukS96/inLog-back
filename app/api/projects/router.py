from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectMemberRead, ProjectRead, ProjectUpdate
from app.schemas.project_invitation import InvitationResponseRequest, ProjectUserInvitationCreate
from app.schemas.user import UserRead
from app.services.project import (
    create_project,
    delete_project,
    get_project,
    list_project_members,
    list_projects,
    update_project,
    user_has_org_access,
)
from app.services.project_invitation import (
    create_project_invitation,
    list_pending_invitations,
    respond_to_invitation,
)
from app.services.user import serialize_user

project_router = APIRouter(prefix="/projects/project", tags=["projects"])
members_router = APIRouter(prefix="/projects", tags=["projects"])


@project_router.get("/", response_model=list[ProjectRead])
async def get_projects(
    organization: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectRead]:
    projects = await list_projects(db, current_user, organization_id=organization)
    return [ProjectRead.model_validate(project) for project in projects]


@project_router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def add_project(
    data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    if not await user_has_org_access(db, current_user, data.organization):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    project = await create_project(db, current_user, data)
    return ProjectRead.model_validate(project)


@project_router.get("/{project_id}/", response_model=ProjectRead)
async def get_project_by_id(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    project = await get_project(db, current_user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    return ProjectRead.model_validate(project)


@project_router.patch("/{project_id}/", response_model=ProjectRead)
async def patch_project(
    project_id: int,
    data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    project = await get_project(db, current_user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    updated_project = await update_project(db, project, data)
    return ProjectRead.model_validate(updated_project)


@project_router.delete("/{project_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def remove_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    project = await get_project(db, current_user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    await delete_project(db, project)


@members_router.get("/{project_id}/members/", response_model=list[ProjectMemberRead])
async def get_project_members(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectMemberRead]:
    project = await get_project(db, current_user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    return await list_project_members(db, current_user, project_id)


@members_router.get("/{project_id}/user-invitation/", response_model=list[UserRead])
async def get_project_invitations(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserRead]:
    project = await get_project(db, current_user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    users = await list_pending_invitations(db, current_user, project_id)
    return [serialize_user(user) for user in users]


@members_router.post(
    "/{project_id}/user-invitation/",
    status_code=status.HTTP_201_CREATED,
)
async def invite_user_to_project(
    project_id: int,
    data: ProjectUserInvitationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        invitation = await create_project_invitation(db, current_user, project_id, data)
    except ValueError as exc:
        error_code = str(exc)
        if error_code == "project_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            ) from exc
        if error_code == "not_project_member":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this project.",
            ) from exc
        if error_code == "cannot_invite_self":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot invite yourself.",
            ) from exc
        if error_code == "already_member":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a project member.",
            ) from exc
        if error_code == "invitee_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            ) from exc
        if error_code == "invitation_exists":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pending invitation already exists.",
            ) from exc
        raise

    return {
        "id": invitation.id,
        "project": invitation.project_id,
        "user": invitation.invitee_id,
        "role": invitation.role,
        "status": invitation.status,
    }


@members_router.post("/{project_id}/user-invitation/response/", status_code=status.HTTP_204_NO_CONTENT)
async def respond_project_invitation(
    project_id: int,
    data: InvitationResponseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await respond_to_invitation(db, current_user, project_id, data)
    except ValueError as exc:
        error_code = str(exc)
        if error_code in {"invitation_not_found", "project_not_found"}:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found.",
            ) from exc
        raise
