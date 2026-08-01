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
    AdminProjectRead,
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
