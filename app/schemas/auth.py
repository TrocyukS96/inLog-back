from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.user import UserRead


class RegistrationRequest(BaseModel):
    email: EmailStr
    password1: str = Field(min_length=8)
    password2: str = Field(min_length=8)
    username: str | None = None
    receive_notifications: bool = False
    receive_advertisement: bool = False
    invitation_token: str = ""
    belonging: str = "common"

    @field_validator("password2")
    @classmethod
    def passwords_match(cls, password2: str, info) -> str:
        password1 = info.data.get("password1")
        if password1 and password1 != password2:
            raise ValueError("Passwords do not match")
        return password2


class RegistrationResponse(BaseModel):
    email: EmailStr
    password1: str
    password2: str
    username: str | None = None
    receive_notifications: bool = False
    receive_advertisement: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    username: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserRead


class TokenVerifyRequest(BaseModel):
    token: str


class TokenVerifyResponse(BaseModel):
    token: str


class VerifyEmailRequest(BaseModel):
    key: str
    uid: str | None = None


class VerifyEmailResponse(BaseModel):
    key: str
    uid: str | None = None
    detail: str | None = None


class ResendEmailRequest(BaseModel):
    email: EmailStr


class ResendEmailResponse(BaseModel):
    email: EmailStr
    detail: str | None = None
