from typing import Literal

from pydantic import BaseModel, Field


class ProjectUserInvitationCreate(BaseModel):
    user: int = Field(description="ID пользователя, которого приглашают")
    role: str = "member"


class InvitationResponseRequest(BaseModel):
    action: Literal["accept", "reject"]
    project_user_invitation: int
