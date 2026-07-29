from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.organization import OrganizationMember
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.project import MemberUserRead, ProjectCreate, ProjectMemberRead, ProjectUpdate


async def user_has_org_access(db: AsyncSession, user: User, organization_id: int) -> bool:
    result = await db.execute(
        select(OrganizationMember.id).where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == organization_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def list_projects(
    db: AsyncSession,
    user: User,
    organization_id: int | None = None,
) -> list[Project]:
    query = (
        select(Project)
        .join(OrganizationMember, OrganizationMember.organization_id == Project.organization_id)
        .where(OrganizationMember.user_id == user.id)
        .order_by(Project.created_at.desc())
    )
    if organization_id is not None:
        query = query.where(Project.organization_id == organization_id)

    result = await db.execute(query)
    return list(result.scalars().unique().all())


async def get_project(db: AsyncSession, user: User, project_id: int) -> Project | None:
    result = await db.execute(
        select(Project)
        .join(OrganizationMember, OrganizationMember.organization_id == Project.organization_id)
        .where(
            Project.id == project_id,
            OrganizationMember.user_id == user.id,
        )
    )
    return result.scalar_one_or_none()


async def create_project(db: AsyncSession, user: User, data: ProjectCreate) -> Project:
    project = Project(
        name=data.name,
        reservoir=data.reservoir,
        company_customer=data.company_customer,
        contractor=data.contractor,
        country=data.country,
        organization_id=data.organization,
    )
    db.add(project)
    await db.flush()

    db.add(
        ProjectMember(
            user_id=user.id,
            project_id=project.id,
            role="admin",
            belonging=user.belonging,
        )
    )
    await db.flush()
    await db.refresh(project)
    return project


async def update_project(db: AsyncSession, project: Project, data: ProjectUpdate) -> Project:
    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(project, field, value)
    await db.flush()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project: Project) -> None:
    await db.delete(project)


def serialize_member_user(user: User) -> MemberUserRead:
    avatar = user.avatar or {}
    return MemberUserRead(
        id=user.id,
        email=user.email,
        name=user.name or "",
        full_name=user.full_name,
        organization=user.company_name or "",
        position=user.position or "",
        mobile_phone=user.phone_number or "",
        work_phone="",
        avatar={
            "small": avatar.get("small") or "",
            "medium": avatar.get("medium") or "",
            "large": avatar.get("large") or "",
            "original": avatar.get("original") or "",
        },
    )


async def list_project_members(
    db: AsyncSession,
    user: User,
    project_id: int,
) -> list[ProjectMemberRead]:
    project = await get_project(db, user, project_id)
    if project is None:
        return []

    result = await db.execute(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .options(selectinload(ProjectMember.user))
        .order_by(ProjectMember.created_at.asc())
    )
    members = result.scalars().all()

    return [
        ProjectMemberRead(
            id=member.id,
            project=member.project_id,
            role=member.role,
            belonging=member.belonging,
            created_at=member.created_at,
            user=serialize_member_user(member.user),
        )
        for member in members
        if member.user is not None
    ]
