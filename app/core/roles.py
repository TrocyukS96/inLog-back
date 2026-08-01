from enum import StrEnum


class PlatformRole(StrEnum):
    """Platform-wide role stored in users.role (not org/project membership)."""

    MEMBER = "member"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


PLATFORM_ADMIN_ROLES: frozenset[str] = frozenset(
    {PlatformRole.ADMIN, PlatformRole.SUPER_ADMIN}
)


def normalize_platform_role(role: str | None) -> str:
    if not role:
        return PlatformRole.MEMBER
    return role


def is_platform_admin(user_role: str | None) -> bool:
    return normalize_platform_role(user_role) in PLATFORM_ADMIN_ROLES


def is_super_admin(user_role: str | None) -> bool:
    return normalize_platform_role(user_role) == PlatformRole.SUPER_ADMIN
