from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ProviderCredentialStatus, ProviderName, ProviderType


class ProviderCredentialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_type: ProviderType
    provider_name: ProviderName
    display_name: str
    masked_summary: str | None = None
    is_active: bool
    status: ProviderCredentialStatus
    last_tested_at: datetime | None = None
    last_test_status: str | None = None
    last_test_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ProviderCredentialListResponse(BaseModel):
    items: list[ProviderCredentialRead]


class ProviderCredentialUpsertRequest(BaseModel):
    provider_type: ProviderType
    provider_name: ProviderName
    config: dict[str, str | int | bool | None] = Field(default_factory=dict)


class ProviderTestResponse(BaseModel):
    success: bool
    message: str
    tested_at: datetime
