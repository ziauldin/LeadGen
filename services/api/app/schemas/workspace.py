from datetime import datetime
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.workspace import WorkspaceRole

_TIMEZONES = available_timezones()


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    plan: str
    timezone: str
    created_at: datetime


class WorkspaceWithRole(WorkspaceRead):
    role: WorkspaceRole


class WorkspaceListResponse(BaseModel):
    items: list[WorkspaceWithRole]
    current_workspace_id: int | None


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    timezone: str = Field(default="UTC", max_length=64)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        if value not in _TIMEZONES:
            raise ValueError("Unknown timezone")
        return value


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    timezone: str | None = Field(default=None, max_length=64)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str | None) -> str | None:
        if value is not None and value not in _TIMEZONES:
            raise ValueError("Unknown timezone")
        return value


class MemberRead(BaseModel):
    user_id: int
    name: str
    email: str
    role: WorkspaceRole
    joined_at: datetime


class MemberUpdate(BaseModel):
    role: WorkspaceRole


class InvitationCreate(BaseModel):
    email: EmailStr
    role: WorkspaceRole = WorkspaceRole.MEMBER


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: WorkspaceRole
    expires_at: datetime
    created_at: datetime


class InvitationPreview(BaseModel):
    workspace_name: str
    email: str
    role: WorkspaceRole
    expires_at: datetime


class OnboardingStatus(BaseModel):
    email_verified: bool
    sender_profile: bool
    sending_provider: bool
    niche_created: bool
    leads_added: bool
    campaign_created: bool
    completed: bool
