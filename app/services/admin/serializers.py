from app.models.user import User
from app.schemas.admin import AdminUserBrief


def user_display_name(user: User | None) -> str:
    if user is None:
        return ""
    return user.full_name or user.email or ""


def serialize_user_brief(user: User | None) -> AdminUserBrief | None:
    if user is None:
        return None

    avatar = user.avatar if isinstance(user.avatar, dict) else {}

    return AdminUserBrief(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        name=user.name,
        surname=user.surname,
        avatar={
            "small": avatar.get("small"),
            "medium": avatar.get("medium"),
        },
    )
