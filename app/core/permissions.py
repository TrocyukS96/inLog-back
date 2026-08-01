from enum import StrEnum

from app.core.roles import PlatformRole, normalize_platform_role


class Permission(StrEnum):
    ACCESS_ADMIN_PANEL = "access_admin_panel"
    VIEW_ALL_USERS = "view_all_users"
    DELETE_USERS = "delete_users"
    MANAGE_USER_ROLES = "manage_user_roles"
    VIEW_ALL_ORGANIZATIONS = "view_all_organizations"
    VIEW_ALL_PROJECTS = "view_all_projects"
    VIEW_ALL_TASKS = "view_all_tasks"
    VIEW_ALL_TASK_STATUSES = "view_all_task_statuses"
    VIEW_ALL_TASK_TAGS = "view_all_task_tags"


ROLE_PERMISSIONS: dict[PlatformRole, frozenset[Permission]] = {
    PlatformRole.MEMBER: frozenset(),
    PlatformRole.ADMIN: frozenset(
        {
            Permission.ACCESS_ADMIN_PANEL,
            Permission.VIEW_ALL_USERS,
            Permission.DELETE_USERS,
            Permission.VIEW_ALL_ORGANIZATIONS,
            Permission.VIEW_ALL_PROJECTS,
            Permission.VIEW_ALL_TASKS,
            Permission.VIEW_ALL_TASK_STATUSES,
            Permission.VIEW_ALL_TASK_TAGS,
        }
    ),
    PlatformRole.SUPER_ADMIN: frozenset(Permission),
}


def permissions_for_role(role: str | None) -> frozenset[Permission]:
    normalized = normalize_platform_role(role)
    try:
        platform_role = PlatformRole(normalized)
    except ValueError:
        return frozenset()
    return ROLE_PERMISSIONS.get(platform_role, frozenset())


def user_has_permission(role: str | None, permission: Permission) -> bool:
    return permission in permissions_for_role(role)


def user_permissions(role: str | None) -> list[str]:
    return sorted(permission.value for permission in permissions_for_role(role))
