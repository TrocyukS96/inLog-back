from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission, user_has_permission
from app.core.roles import PlatformRole, is_super_admin, normalize_platform_role
from app.models.organization import Organization, OrganizationMember
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.admin import AdminUserRead, PaginatedAdminUsersResponse
from app.services.admin.pagination import build_page_urls


def serialize_admin_user(user: User) -> AdminUserRead:
    return AdminUserRead(
        id=user.id,
        email=user.email,
        role=normalize_platform_role(user.role),
        full_name=user.full_name,
        name=user.name,
        surname=user.surname,
        is_active=user.is_active,
        is_email_verified=user.is_email_verified,
        created_at=user.created_at,
    )


async def list_all_users(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
    base_path: str,
) -> PaginatedAdminUsersResponse:
    filters = []
    if search:
        pattern = f"%{search.strip().lower()}%"
        filters.append(
            (User.email.ilike(pattern))
            | (User.name.ilike(pattern))
            | (User.surname.ilike(pattern))
        )

    count_query = select(func.count()).select_from(User)
    if filters:
        count_query = count_query.where(*filters)
    total = int((await db.execute(count_query)).scalar_one())

    query = select(User).order_by(User.created_at.desc(), User.id.desc())
    if filters:
        query = query.where(*filters)

    result = await db.execute(query.limit(limit).offset(offset))
    users = list(result.scalars().all())

    query_suffix = f"search={search}" if search else ""
    next_url, previous_url = build_page_urls(
        base_path=base_path,
        limit=limit,
        offset=offset,
        total=total,
        query_suffix=query_suffix,
    )

    return PaginatedAdminUsersResponse(
        count=total,
        next=next_url,
        previous=previous_url,
        results=[serialize_admin_user(user) for user in users],
    )


def _can_delete_user(actor: User, target: User) -> None:
    if actor.id == target.id:
        raise ValueError("You cannot delete your own account.")

    actor_role = normalize_platform_role(actor.role)
    target_role = normalize_platform_role(target.role)

    if target_role == PlatformRole.SUPER_ADMIN and actor_role != PlatformRole.SUPER_ADMIN:
        raise ValueError("Super admin accounts can only be deleted by another super admin.")
    if target_role == PlatformRole.ADMIN and actor_role != PlatformRole.SUPER_ADMIN:
        raise ValueError("Only super admins can delete admin accounts.")

    if not user_has_permission(actor.role, Permission.DELETE_USERS):
        raise ValueError("Insufficient permissions to delete users.")


async def delete_user_by_admin(db: AsyncSession, actor: User, user_id: int) -> None:
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if target is None:
        raise ValueError("User not found.")

    _can_delete_user(actor, target)

    single_member_orgs = (
        select(OrganizationMember.organization_id)
        .group_by(OrganizationMember.organization_id)
        .having(func.count() == 1)
    )
    orphan_orgs = list(
        (
            await db.execute(
                select(OrganizationMember.organization_id).where(
                    OrganizationMember.user_id == user_id,
                    OrganizationMember.organization_id.in_(single_member_orgs),
                )
            )
        ).scalars().all()
    )

    await db.execute(delete(User).where(User.id == user_id))

    if orphan_orgs:
        await db.execute(delete(Organization).where(Organization.id.in_(orphan_orgs)))


def _can_manage_role(actor: User, new_role: str, target: User | None = None) -> None:
    if not user_has_permission(actor.role, Permission.MANAGE_USER_ROLES):
        raise ValueError("Only super admins can change platform roles.")

    try:
        PlatformRole(new_role)
    except ValueError as exc:
        raise ValueError(
            f"Invalid role. Allowed values: {', '.join(role.value for role in PlatformRole)}."
        ) from exc

    if new_role == PlatformRole.SUPER_ADMIN:
        raise ValueError("Super admin role can only be assigned via server configuration.")

    if target is not None:
        target_role = normalize_platform_role(target.role)
        if target_role == PlatformRole.SUPER_ADMIN:
            raise ValueError("Super admin role cannot be changed via API.")
        if target.id == actor.id:
            raise ValueError("You cannot change your own platform role.")


async def update_user_platform_role(
    db: AsyncSession,
    actor: User,
    user_id: int,
    new_role: str,
) -> AdminUserRead:
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if target is None:
        raise ValueError("User not found.")

    _can_manage_role(actor, new_role, target)
    target.role = new_role
    await db.flush()
    await db.refresh(target)
    return serialize_admin_user(target)


async def ensure_super_admin_email(db: AsyncSession, email: str) -> bool:
    normalized_email = email.strip().lower()
    if not normalized_email:
        return False

    result = await db.execute(select(User).where(User.email == normalized_email))
    user = result.scalar_one_or_none()
    if user is None:
        return False

    if normalize_platform_role(user.role) == PlatformRole.SUPER_ADMIN:
        return False

    user.role = PlatformRole.SUPER_ADMIN
    await db.flush()
    return True
