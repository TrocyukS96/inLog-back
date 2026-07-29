from app.models.user import DEFAULT_USER_SETTINGS, User
from app.schemas.user import AvatarSchema, UserRead, UserSettingsSchema


def serialize_user(user: User) -> UserRead:
    avatar_data = user.avatar or {}
    settings_data = user.settings or DEFAULT_USER_SETTINGS

    return UserRead(
        id=user.id,
        email=user.email,
        name=user.name or "",
        patronymic=user.patronymic or "",
        surname=user.surname or "",
        full_name=user.full_name,
        company_name=user.company_name or "",
        position=user.position or "",
        about_myself=user.about_myself or "",
        role=user.role or "member",
        avatar=AvatarSchema(**avatar_data) if avatar_data else AvatarSchema(),
        phone_number=user.phone_number,
        settings=UserSettingsSchema(**settings_data),
        belonging=user.belonging or "common",
    )
