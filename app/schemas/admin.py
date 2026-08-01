from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PaginatedResponse(BaseModel):
    count: int
    next: str | None
    previous: str | None


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: str
    full_name: str = ""
    name: str = ""
    surname: str = ""
    is_active: bool
    is_email_verified: bool
    created_at: datetime


class PaginatedAdminUsersResponse(PaginatedResponse):
    results: list[AdminUserRead]


class AdminUserRoleUpdate(BaseModel):
    role: str = Field(min_length=1, max_length=50)


class AdminOrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    short_name: str
    address: str
    inn: str | None = None
    kpp: str | None = None
    created_at: datetime
    members_count: int = 0
    projects_count: int = 0


class PaginatedAdminOrganizationsResponse(PaginatedResponse):
    results: list[AdminOrganizationRead]


class AdminProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    organization_id: int
    organization_name: str = ""
    reservoir: str = ""
    company_customer: str = ""
    contractor: str = ""
    country: str = ""
    created_at: datetime
    members_count: int = 0


class PaginatedAdminProjectsResponse(PaginatedResponse):
    results: list[AdminProjectRead]


class AdminTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    project_id: int
    project_name: str = ""
    creator_id: int
    creator_email: str = ""
    status_id: int
    status_name_en: str = ""
    status_name_ru: str = ""
    priority: str
    archived: bool
    is_template: bool
    parent_id: int | None = None
    created_at: datetime


class PaginatedAdminTasksResponse(PaginatedResponse):
    results: list[AdminTaskRead]


class AdminTaskStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    project_name: str = ""
    name_en: str
    name_ru: str
    position: int
    created_at: datetime


class PaginatedAdminTaskStatusesResponse(PaginatedResponse):
    results: list[AdminTaskStatusRead]


class AdminTaskTagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    project_name: str = ""
    name: str
    is_systemic: bool
    is_orphan: bool
    created_at: datetime


class PaginatedAdminTaskTagsResponse(PaginatedResponse):
    results: list[AdminTaskTagRead]


class AdminAccessRead(BaseModel):
    role: str
    is_platform_admin: bool
    is_super_admin: bool
    permissions: list[str]
