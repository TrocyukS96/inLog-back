from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.organization import Organization, OrganizationMember
from app.models.project import Project, ProjectMember
from app.models.task import Task, TaskStatus, TaskTag
from app.models.user import User
from app.schemas.admin import (
    AdminMemberRead,
    AdminOrganizationRead,
    AdminOrganizationUpdate,
    AdminProjectRead,
    AdminProjectUpdate,
    AdminTaskRead,
    AdminTaskStatusRead,
    AdminTaskTagRead,
    AdminUserBrief,
    PaginatedAdminMembersResponse,
    PaginatedAdminOrganizationsResponse,
    PaginatedAdminProjectsResponse,
    PaginatedAdminTaskStatusesResponse,
    PaginatedAdminTaskTagsResponse,
    PaginatedAdminTasksResponse,
)
from app.services.admin.pagination import build_page_urls
from app.services.admin.serializers import serialize_user_brief, user_display_name
from app.services.organization import delete_organization
from app.services.project import delete_project
from app.services.task import delete_task


async def _load_project_members_map(
    db: AsyncSession,
    project_ids: list[int],
) -> dict[int, list[AdminUserBrief]]:
    if not project_ids:
        return {}

    result = await db.execute(
        select(ProjectMember)
        .where(ProjectMember.project_id.in_(project_ids))
        .options(selectinload(ProjectMember.user))
        .order_by(ProjectMember.project_id.asc(), ProjectMember.created_at.asc())
    )
    members = list(result.scalars().unique().all())

    members_map: dict[int, list[AdminUserBrief]] = {project_id: [] for project_id in project_ids}
    seen: dict[int, set[int]] = {project_id: set() for project_id in project_ids}

    for member in members:
        user_brief = serialize_user_brief(member.user)
        if user_brief is None:
            continue
        if member.user_id in seen[member.project_id]:
            continue
        seen[member.project_id].add(member.user_id)
        members_map[member.project_id].append(user_brief)

    return members_map


async def list_all_members(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
    membership_type: str = "project",
    organization_id: int | None = None,
    project_id: int | None = None,
    base_path: str,
) -> PaginatedAdminMembersResponse:
    if membership_type == "organization":
        return await _list_organization_members(
            db,
            limit=limit,
            offset=offset,
            search=search,
            organization_id=organization_id,
            base_path=base_path,
        )

    return await _list_project_members(
        db,
        limit=limit,
        offset=offset,
        search=search,
        organization_id=organization_id,
        project_id=project_id,
        base_path=base_path,
    )


async def _list_project_members(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    search: str | None,
    organization_id: int | None,
    project_id: int | None,
    base_path: str,
) -> PaginatedAdminMembersResponse:
    filters = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            User.email.ilike(pattern)
            | User.name.ilike(pattern)
            | User.surname.ilike(pattern)
            | Project.name.ilike(pattern)
        )
    if organization_id is not None:
        filters.append(Project.organization_id == organization_id)
    if project_id is not None:
        filters.append(ProjectMember.project_id == project_id)

    count_query = (
        select(func.count())
        .select_from(ProjectMember)
        .join(ProjectMember.user)
        .join(ProjectMember.project)
    )
    if filters:
        count_query = count_query.where(*filters)
    total = int((await db.execute(count_query)).scalar_one())

    query = (
        select(ProjectMember)
        .join(ProjectMember.user)
        .join(ProjectMember.project)
        .join(Project.organization)
        .options(
            selectinload(ProjectMember.user),
            selectinload(ProjectMember.project).selectinload(Project.organization),
        )
        .order_by(ProjectMember.created_at.desc(), ProjectMember.id.desc())
    )
    if filters:
        query = query.where(*filters)

    result = await db.execute(query.limit(limit).offset(offset))
    project_members = list(result.scalars().unique().all())

    query_parts = _member_query_suffix(
        search=search,
        membership_type="project",
        organization_id=organization_id,
        project_id=project_id,
    )
    next_url, previous_url = build_page_urls(
        base_path=base_path,
        limit=limit,
        offset=offset,
        total=total,
        query_suffix=query_parts,
    )

    return PaginatedAdminMembersResponse(
        count=total,
        next=next_url,
        previous=previous_url,
        results=[
            AdminMemberRead(
                id=member.id,
                membership_type="project",
                role=member.role,
                belonging=member.belonging,
                organization_id=member.project.organization_id,
                organization_name=member.project.organization.short_name
                if member.project.organization
                else "",
                project_id=member.project_id,
                project_name=member.project.name if member.project else "",
                user=serialize_user_brief(member.user) or AdminUserBrief(
                    id=member.user_id,
                    email=member.user.email if member.user else f"user-{member.user_id}@unknown.local",
                ),
                created_at=member.created_at,
            )
            for member in project_members
        ],
    )


async def _list_organization_members(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    search: str | None,
    organization_id: int | None,
    base_path: str,
) -> PaginatedAdminMembersResponse:
    filters = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            User.email.ilike(pattern)
            | User.name.ilike(pattern)
            | User.surname.ilike(pattern)
            | Organization.full_name.ilike(pattern)
            | Organization.short_name.ilike(pattern)
        )
    if organization_id is not None:
        filters.append(OrganizationMember.organization_id == organization_id)

    count_query = (
        select(func.count())
        .select_from(OrganizationMember)
        .join(OrganizationMember.user)
        .join(OrganizationMember.organization)
    )
    if filters:
        count_query = count_query.where(*filters)
    total = int((await db.execute(count_query)).scalar_one())

    query = (
        select(OrganizationMember)
        .join(OrganizationMember.user)
        .join(OrganizationMember.organization)
        .options(
            selectinload(OrganizationMember.user),
            selectinload(OrganizationMember.organization),
        )
        .order_by(OrganizationMember.created_at.desc(), OrganizationMember.id.desc())
    )
    if filters:
        query = query.where(*filters)

    result = await db.execute(query.limit(limit).offset(offset))
    org_members = list(result.scalars().unique().all())

    query_parts = _member_query_suffix(
        search=search,
        membership_type="organization",
        organization_id=organization_id,
        project_id=None,
    )
    next_url, previous_url = build_page_urls(
        base_path=base_path,
        limit=limit,
        offset=offset,
        total=total,
        query_suffix=query_parts,
    )

    return PaginatedAdminMembersResponse(
        count=total,
        next=next_url,
        previous=previous_url,
        results=[
            AdminMemberRead(
                id=member.id,
                membership_type="organization",
                role=member.role,
                organization_id=member.organization_id,
                organization_name=member.organization.short_name if member.organization else "",
                user=serialize_user_brief(member.user) or AdminUserBrief(
                    id=member.user_id,
                    email=member.user.email if member.user else f"user-{member.user_id}@unknown.local",
                ),
                created_at=member.created_at,
            )
            for member in org_members
        ],
    )


def _member_query_suffix(
    *,
    search: str | None,
    membership_type: str,
    organization_id: int | None,
    project_id: int | None,
) -> str:
    query_parts = [f"type={membership_type}"]
    if search:
        query_parts.append(f"search={search}")
    if organization_id is not None:
        query_parts.append(f"organization={organization_id}")
    if project_id is not None:
        query_parts.append(f"project={project_id}")
    return "&".join(query_parts)


async def list_all_organizations(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
    base_path: str,
) -> PaginatedAdminOrganizationsResponse:
    filters = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            Organization.full_name.ilike(pattern) | Organization.short_name.ilike(pattern)
        )

    count_query = select(func.count()).select_from(Organization)
    if filters:
        count_query = count_query.where(*filters)
    total = int((await db.execute(count_query)).scalar_one())

    query = select(Organization).order_by(Organization.created_at.desc(), Organization.id.desc())
    if filters:
        query = query.where(*filters)

    result = await db.execute(query.limit(limit).offset(offset))
    organizations = list(result.scalars().all())

    org_ids = [org.id for org in organizations]
    members_counts: dict[int, int] = {}
    projects_counts: dict[int, int] = {}

    if org_ids:
        members_result = await db.execute(
            select(OrganizationMember.organization_id, func.count())
            .where(OrganizationMember.organization_id.in_(org_ids))
            .group_by(OrganizationMember.organization_id)
        )
        members_counts = {org_id: count for org_id, count in members_result.all()}

        projects_result = await db.execute(
            select(Project.organization_id, func.count())
            .where(Project.organization_id.in_(org_ids))
            .group_by(Project.organization_id)
        )
        projects_counts = {org_id: count for org_id, count in projects_result.all()}

    query_suffix = f"search={search}" if search else ""
    next_url, previous_url = build_page_urls(
        base_path=base_path,
        limit=limit,
        offset=offset,
        total=total,
        query_suffix=query_suffix,
    )

    return PaginatedAdminOrganizationsResponse(
        count=total,
        next=next_url,
        previous=previous_url,
        results=[
            AdminOrganizationRead(
                id=org.id,
                full_name=org.full_name,
                short_name=org.short_name,
                address=org.address,
                inn=org.inn,
                kpp=org.kpp,
                created_at=org.created_at,
                members_count=members_counts.get(org.id, 0),
                projects_count=projects_counts.get(org.id, 0),
            )
            for org in organizations
        ],
    )


async def list_all_projects(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
    organization_id: int | None = None,
    base_path: str,
) -> PaginatedAdminProjectsResponse:
    filters = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(Project.name.ilike(pattern))
    if organization_id is not None:
        filters.append(Project.organization_id == organization_id)

    count_query = select(func.count()).select_from(Project)
    if filters:
        count_query = count_query.where(*filters)
    total = int((await db.execute(count_query)).scalar_one())

    query = (
        select(Project)
        .options(selectinload(Project.organization))
        .order_by(Project.created_at.desc(), Project.id.desc())
    )
    if filters:
        query = query.where(*filters)

    result = await db.execute(query.limit(limit).offset(offset))
    projects = list(result.scalars().unique().all())

    project_ids = [project.id for project in projects]
    members_counts: dict[int, int] = {}
    if project_ids:
        members_result = await db.execute(
            select(ProjectMember.project_id, func.count())
            .where(ProjectMember.project_id.in_(project_ids))
            .group_by(ProjectMember.project_id)
        )
        members_counts = {project_id: count for project_id, count in members_result.all()}

    query_parts: list[str] = []
    if search:
        query_parts.append(f"search={search}")
    if organization_id is not None:
        query_parts.append(f"organization={organization_id}")

    next_url, previous_url = build_page_urls(
        base_path=base_path,
        limit=limit,
        offset=offset,
        total=total,
        query_suffix="&".join(query_parts),
    )

    return PaginatedAdminProjectsResponse(
        count=total,
        next=next_url,
        previous=previous_url,
        results=[
            AdminProjectRead(
                id=project.id,
                name=project.name,
                organization_id=project.organization_id,
                organization_name=project.organization.short_name if project.organization else "",
                reservoir=project.reservoir,
                company_customer=project.company_customer,
                contractor=project.contractor,
                country=project.country,
                created_at=project.created_at,
                members_count=members_counts.get(project.id, 0),
            )
            for project in projects
        ],
    )


async def list_all_tasks(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
    project_id: int | None = None,
    base_path: str,
) -> PaginatedAdminTasksResponse:
    filters = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(Task.name.ilike(pattern) | Task.slug.ilike(pattern))
    if project_id is not None:
        filters.append(Task.project_id == project_id)

    count_query = select(func.count()).select_from(Task)
    if filters:
        count_query = count_query.where(*filters)
    total = int((await db.execute(count_query)).scalar_one())

    query = (
        select(Task)
        .options(
            selectinload(Task.creator),
            selectinload(Task.status),
            selectinload(Task.project).selectinload(Project.organization),
        )
        .order_by(Task.created_at.desc(), Task.id.desc())
    )
    if filters:
        query = query.where(*filters)

    result = await db.execute(query.limit(limit).offset(offset))
    tasks = list(result.scalars().unique().all())

    project_ids = list({task.project_id for task in tasks})
    members_map = await _load_project_members_map(db, project_ids)

    query_parts: list[str] = []
    if search:
        query_parts.append(f"search={search}")
    if project_id is not None:
        query_parts.append(f"project={project_id}")

    next_url, previous_url = build_page_urls(
        base_path=base_path,
        limit=limit,
        offset=offset,
        total=total,
        query_suffix="&".join(query_parts),
    )

    return PaginatedAdminTasksResponse(
        count=total,
        next=next_url,
        previous=previous_url,
        results=[
            AdminTaskRead(
                id=task.id,
                name=task.name,
                slug=task.slug,
                project_id=task.project_id,
                project_name=task.project.name if task.project else "",
                organization_id=task.project.organization_id if task.project else None,
                organization_name=(
                    task.project.organization.short_name
                    if task.project and task.project.organization
                    else ""
                ),
                creator_id=task.creator_id,
                creator_email=task.creator.email if task.creator else "",
                creator_name=user_display_name(task.creator),
                creator=serialize_user_brief(task.creator),
                members=members_map.get(task.project_id, []),
                status_id=task.status_id,
                status_name_en=task.status.name_en if task.status else "",
                status_name_ru=task.status.name_ru if task.status else "",
                priority=task.priority,
                archived=task.archived,
                is_template=task.is_template,
                parent_id=task.parent_id,
                created_at=task.created_at,
            )
            for task in tasks
        ],
    )


async def list_all_task_statuses(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    project_id: int | None = None,
    base_path: str,
) -> PaginatedAdminTaskStatusesResponse:
    filters = []
    if project_id is not None:
        filters.append(TaskStatus.project_id == project_id)

    count_query = select(func.count()).select_from(TaskStatus)
    if filters:
        count_query = count_query.where(*filters)
    total = int((await db.execute(count_query)).scalar_one())

    query = (
        select(TaskStatus)
        .options(selectinload(TaskStatus.project))
        .order_by(TaskStatus.project_id.asc(), TaskStatus.position.asc(), TaskStatus.id.asc())
    )
    if filters:
        query = query.where(*filters)

    result = await db.execute(query.limit(limit).offset(offset))
    statuses = list(result.scalars().unique().all())

    query_suffix = f"project={project_id}" if project_id is not None else ""
    next_url, previous_url = build_page_urls(
        base_path=base_path,
        limit=limit,
        offset=offset,
        total=total,
        query_suffix=query_suffix,
    )

    return PaginatedAdminTaskStatusesResponse(
        count=total,
        next=next_url,
        previous=previous_url,
        results=[
            AdminTaskStatusRead(
                id=status.id,
                project_id=status.project_id,
                project_name=status.project.name if status.project else "",
                name_en=status.name_en,
                name_ru=status.name_ru,
                position=status.position,
                created_at=status.created_at,
            )
            for status in statuses
        ],
    )


async def list_all_task_tags(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    project_id: int | None = None,
    search: str | None = None,
    base_path: str,
) -> PaginatedAdminTaskTagsResponse:
    filters = []
    if project_id is not None:
        filters.append(TaskTag.project_id == project_id)
    if search:
        filters.append(TaskTag.name.ilike(f"%{search.strip()}%"))

    count_query = select(func.count()).select_from(TaskTag)
    if filters:
        count_query = count_query.where(*filters)
    total = int((await db.execute(count_query)).scalar_one())

    query = (
        select(TaskTag)
        .options(selectinload(TaskTag.project))
        .order_by(TaskTag.project_id.asc(), TaskTag.name.asc(), TaskTag.id.asc())
    )
    if filters:
        query = query.where(*filters)

    result = await db.execute(query.limit(limit).offset(offset))
    tags = list(result.scalars().unique().all())

    query_parts: list[str] = []
    if project_id is not None:
        query_parts.append(f"project={project_id}")
    if search:
        query_parts.append(f"search={search}")

    next_url, previous_url = build_page_urls(
        base_path=base_path,
        limit=limit,
        offset=offset,
        total=total,
        query_suffix="&".join(query_parts),
    )

    return PaginatedAdminTaskTagsResponse(
        count=total,
        next=next_url,
        previous=previous_url,
        results=[
            AdminTaskTagRead(
                id=tag.id,
                project_id=tag.project_id,
                project_name=tag.project.name if tag.project else "",
                name=tag.name,
                is_systemic=tag.is_systemic,
                is_orphan=tag.is_orphan,
                created_at=tag.created_at,
            )
            for tag in tags
        ],
    )


async def _get_organization_counts(db: AsyncSession, organization_id: int) -> tuple[int, int]:
    members_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(OrganizationMember)
                .where(OrganizationMember.organization_id == organization_id)
            )
        ).scalar_one()
    )
    projects_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Project)
                .where(Project.organization_id == organization_id)
            )
        ).scalar_one()
    )
    return members_count, projects_count


async def _serialize_admin_organization(
    db: AsyncSession,
    organization: Organization,
) -> AdminOrganizationRead:
    members_count, projects_count = await _get_organization_counts(db, organization.id)
    return AdminOrganizationRead(
        id=organization.id,
        full_name=organization.full_name,
        short_name=organization.short_name,
        address=organization.address,
        inn=organization.inn,
        kpp=organization.kpp,
        created_at=organization.created_at,
        members_count=members_count,
        projects_count=projects_count,
    )


async def get_admin_organization(db: AsyncSession, organization_id: int) -> Organization | None:
    result = await db.execute(select(Organization).where(Organization.id == organization_id))
    return result.scalar_one_or_none()


async def update_admin_organization(
    db: AsyncSession,
    organization_id: int,
    data: AdminOrganizationUpdate,
) -> AdminOrganizationRead:
    organization = await get_admin_organization(db, organization_id)
    if organization is None:
        raise ValueError("Organization not found.")

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(organization, field, value)

    await db.flush()
    await db.refresh(organization)
    return await _serialize_admin_organization(db, organization)


async def delete_admin_organization(db: AsyncSession, organization_id: int) -> None:
    organization = await get_admin_organization(db, organization_id)
    if organization is None:
        raise ValueError("Organization not found.")

    await delete_organization(db, organization)


async def _get_project_members_count(db: AsyncSession, project_id: int) -> int:
    return int(
        (
            await db.execute(
                select(func.count())
                .select_from(ProjectMember)
                .where(ProjectMember.project_id == project_id)
            )
        ).scalar_one()
    )


async def _serialize_admin_project(db: AsyncSession, project: Project) -> AdminProjectRead:
    if project.organization is None:
        result = await db.execute(
            select(Project)
            .where(Project.id == project.id)
            .options(selectinload(Project.organization))
        )
        project = result.scalar_one()

    members_count = await _get_project_members_count(db, project.id)
    return AdminProjectRead(
        id=project.id,
        name=project.name,
        organization_id=project.organization_id,
        organization_name=project.organization.short_name if project.organization else "",
        reservoir=project.reservoir,
        company_customer=project.company_customer,
        contractor=project.contractor,
        country=project.country,
        created_at=project.created_at,
        members_count=members_count,
    )


async def get_admin_project(db: AsyncSession, project_id: int) -> Project | None:
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.organization))
    )
    return result.scalar_one_or_none()


async def update_admin_project(
    db: AsyncSession,
    project_id: int,
    data: AdminProjectUpdate,
) -> AdminProjectRead:
    project = await get_admin_project(db, project_id)
    if project is None:
        raise ValueError("Project not found.")

    updates = data.model_dump(exclude_unset=True)
    if "organization_id" in updates:
        organization_id = updates.pop("organization_id")
        organization = await get_admin_organization(db, organization_id)
        if organization is None:
            raise ValueError("Organization not found.")
        project.organization_id = organization_id

    for field, value in updates.items():
        setattr(project, field, value)

    await db.flush()
    await db.refresh(project)
    return await _serialize_admin_project(db, project)


async def delete_admin_project(db: AsyncSession, project_id: int) -> None:
    project = await get_admin_project(db, project_id)
    if project is None:
        raise ValueError("Project not found.")

    await delete_project(db, project)


async def get_admin_task(db: AsyncSession, task_id: int) -> Task | None:
    result = await db.execute(select(Task).where(Task.id == task_id))
    return result.scalar_one_or_none()


async def delete_admin_task(db: AsyncSession, task_id: int) -> None:
    task = await get_admin_task(db, task_id)
    if task is None:
        raise ValueError("Task not found.")

    await delete_task(db, task)


async def get_admin_task_status(db: AsyncSession, status_id: int) -> TaskStatus | None:
    result = await db.execute(select(TaskStatus).where(TaskStatus.id == status_id))
    return result.scalar_one_or_none()


async def delete_admin_task_status(db: AsyncSession, status_id: int) -> None:
    status = await get_admin_task_status(db, status_id)
    if status is None:
        raise ValueError("Task status not found.")

    tasks_count = int(
        (
            await db.execute(
                select(func.count()).select_from(Task).where(Task.status_id == status_id)
            )
        ).scalar_one()
    )
    if tasks_count > 0:
        raise ValueError("Cannot delete task status while tasks are assigned to it.")

    await db.delete(status)
    await db.flush()


async def get_admin_task_tag(db: AsyncSession, tag_id: int) -> TaskTag | None:
    result = await db.execute(select(TaskTag).where(TaskTag.id == tag_id))
    return result.scalar_one_or_none()


async def delete_admin_task_tag(db: AsyncSession, tag_id: int) -> None:
    tag = await get_admin_task_tag(db, tag_id)
    if tag is None:
        raise ValueError("Task tag not found.")

    await db.delete(tag)
    await db.flush()
