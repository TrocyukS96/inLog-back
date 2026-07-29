from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1)
    organization: int
    reservoir: str = ""
    company_customer: str = ""
    contractor: str = ""
    country: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = None
    reservoir: str | None = None
    company_customer: str | None = None
    contractor: str | None = None
    country: str | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    reservoir: str
    company_customer: str
    contractor: str
    country: str
    created_at: datetime


class MemberUserRead(BaseModel):
    id: int
    email: str
    name: str
    full_name: str
    organization: str
    position: str
    mobile_phone: str
    work_phone: str
    avatar: dict


class ProjectMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project: int
    role: str
    belonging: str
    created_at: datetime
    user: MemberUserRead
