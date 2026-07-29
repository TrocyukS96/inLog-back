from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AvatarSchema(BaseModel):
    small: str | None = None
    medium: str | None = None
    large: str | None = None
    original: str | None = None


class UserSettingsSchema(BaseModel):
    language: str = "ru"
    timezone: str = "Europe/Moscow"
    sound_notification: bool | str = True
    disabled_email_notifications: list[str] = Field(default_factory=list)
    disabled_inlog_notifications: list[str] = Field(default_factory=list)
    notifiable_days_of_week: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    notify_from_time: str = "09:00"
    notify_to_time: str = "18:00"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str = ""
    patronymic: str = ""
    surname: str = ""
    full_name: str = ""
    company_name: str = ""
    position: str = ""
    about_myself: str = ""
    role: str = "member"
    avatar: AvatarSchema = Field(default_factory=AvatarSchema)
    phone_number: str | None = None
    settings: UserSettingsSchema = Field(default_factory=UserSettingsSchema)
    belonging: str = "common"
