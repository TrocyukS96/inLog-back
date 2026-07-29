from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.organization import OrganizationMember
from app.models.project import Project, ProjectMember
from app.models.project_invitation import (
    INVITATION_ACCEPTED,
    INVITATION_PENDING,
    INVITATION_REJECTED,
    ProjectUserInvitation,
)
from app.models.user import User
from app.schemas.project_invitation import InvitationResponseRequest, ProjectUserInvitationCreate
from app.services.notification import create_notification
from app.services.project import get_project


async def user_is_project_member(db: AsyncSession, user_id: int, project_id: int) -> bool:
    result = await db.execute(
        select(ProjectMember.id).where(
            ProjectMember.user_id == user_id,
            ProjectMember.project_id == project_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def ensure_org_membership(
    db: AsyncSession,
    user: User,
    organization_id: int,
    role: str = "member",
) -> None:
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == organization_id,
        )
    )
    if result.scalar_one_or_none() is None:
        db.add(
            OrganizationMember(
                user_id=user.id,
                organization_id=organization_id,
                role=role,
            )
        )
        await db.flush()


def build_invitation_notification_data(
    project: Project,
    invitation: ProjectUserInvitation,
) -> dict:
    return {
        "project": {"id": project.id, "name": project.name},
        "project_user_invitation": {"id": invitation.id, "role": invitation.role},
    }


def build_invitation_response_notification_data(
    project: Project,
    invitation: ProjectUserInvitation,
    *,
    accepted: bool,
) -> dict:
    return {
        "project": {"id": project.id, "name": project.name},
        "accepted": accepted,
        "project_user_invitation": {"id": invitation.id, "role": invitation.role},
    }


async def create_project_invitation(
    db: AsyncSession,
    current_user: User,
    project_id: int,
    data: ProjectUserInvitationCreate,
) -> ProjectUserInvitation:
    project = await get_project(db, current_user, project_id)
    if project is None:
        raise ValueError("project_not_found")

    if not await user_is_project_member(db, current_user.id, project_id):
        raise ValueError("not_project_member")

    if data.user == current_user.id:
        raise ValueError("cannot_invite_self")

    if await user_is_project_member(db, data.user, project_id):
        raise ValueError("already_member")

    invitee_result = await db.execute(select(User).where(User.id == data.user))
    invitee = invitee_result.scalar_one_or_none()
    if invitee is None or not invitee.is_active:
        raise ValueError("invitee_not_found")

    pending_result = await db.execute(
        select(ProjectUserInvitation).where(
            ProjectUserInvitation.project_id == project_id,
            ProjectUserInvitation.invitee_id == data.user,
            ProjectUserInvitation.status == INVITATION_PENDING,
        )
    )
    if pending_result.scalar_one_or_none() is not None:
        raise ValueError("invitation_exists")

    invitation = ProjectUserInvitation(
        project_id=project_id,
        inviter_id=current_user.id,
        invitee_id=data.user,
        role=data.role,
        status=INVITATION_PENDING,
    )
    db.add(invitation)
    await db.flush()
    await db.refresh(invitation)

    await create_notification(
        db,
        receiver_id=invitee.id,
        sender_id=current_user.id,
        notification_type="project_user_invitation",
        data=build_invitation_notification_data(project, invitation),
    )

    return invitation


async def list_pending_invitations(
    db: AsyncSession,
    current_user: User,
    project_id: int,
) -> list[User]:
    project = await get_project(db, current_user, project_id)
    if project is None:
        return []

    result = await db.execute(
        select(ProjectUserInvitation)
        .where(
            ProjectUserInvitation.project_id == project_id,
            ProjectUserInvitation.status == INVITATION_PENDING,
        )
        .options(selectinload(ProjectUserInvitation.invitee))
        .order_by(ProjectUserInvitation.created_at.desc())
    )
    invitations = result.scalars().all()
    users: list[User] = []
    for invitation in invitations:
        if invitation.invitee is not None:
            users.append(invitation.invitee)
    return users


async def respond_to_invitation(
    db: AsyncSession,
    current_user: User,
    project_id: int,
    data: InvitationResponseRequest,
) -> None:
    result = await db.execute(
        select(ProjectUserInvitation)
        .where(
            ProjectUserInvitation.id == data.project_user_invitation,
            ProjectUserInvitation.project_id == project_id,
            ProjectUserInvitation.invitee_id == current_user.id,
            ProjectUserInvitation.status == INVITATION_PENDING,
        )
        .options(
            selectinload(ProjectUserInvitation.project),
            selectinload(ProjectUserInvitation.inviter),
        )
    )
    invitation = result.scalar_one_or_none()
    if invitation is None:
        raise ValueError("invitation_not_found")

    project = invitation.project
    if project is None:
        raise ValueError("project_not_found")

    accepted = data.action == "accept"

    if accepted:
        await ensure_org_membership(db, current_user, project.organization_id)
        if not await user_is_project_member(db, current_user.id, project_id):
            db.add(
                ProjectMember(
                    user_id=current_user.id,
                    project_id=project_id,
                    role=invitation.role,
                    belonging=current_user.belonging,
                )
            )
        invitation.status = INVITATION_ACCEPTED
    else:
        invitation.status = INVITATION_REJECTED

    await db.flush()

    if invitation.inviter_id:
        await create_notification(
            db,
            receiver_id=invitation.inviter_id,
            sender_id=current_user.id,
            notification_type="project_user_invitation_response",
            data=build_invitation_response_notification_data(
                project,
                invitation,
                accepted=accepted,
            ),
        )
