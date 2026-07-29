from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    full_name: str = Field(min_length=1)
    short_name: str = Field(min_length=1)
    address: str = ""
    inn: str | None = None
    kpp: str | None = None


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    short_name: str
    address: str
    inn: str | None = None
    kpp: str | None = None
    created_at: datetime
