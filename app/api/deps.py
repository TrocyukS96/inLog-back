from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission, permissions_for_role, user_has_permission
from app.core.roles import is_platform_admin, is_super_admin, normalize_platform_role
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.services.auth import get_user_by_id

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
        )

    try:
        payload = decode_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        ) from exc

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type.",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
        )

    user = await get_user_by_id(db, int(user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )

    return user


def require_permission(permission: Permission) -> Callable[..., Any]:
    async def _require_permission(user: User = Depends(get_current_user)) -> User:
        if not user_has_permission(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )
        return user

    return _require_permission


async def require_platform_admin(user: User = Depends(get_current_user)) -> User:
    if not is_platform_admin(user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return user


async def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if not is_super_admin(user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required.",
        )
    return user


def get_admin_access_payload(user: User) -> dict[str, Any]:
    role = normalize_platform_role(user.role)
    return {
        "role": role,
        "is_platform_admin": is_platform_admin(role),
        "is_super_admin": is_super_admin(role),
        "permissions": sorted(permission.value for permission in permissions_for_role(role)),
    }
