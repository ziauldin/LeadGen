from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SuppressionCreate(BaseModel):
    email: str | None = Field(default=None, max_length=255)
    domain: str | None = Field(default=None, max_length=255)
    reason: str | None = Field(default=None, max_length=500)
    source: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def require_email_or_domain(self) -> "SuppressionCreate":
        if not self.email and not self.domain:
            raise ValueError("Either email or domain is required")
        return self


class SuppressionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str | None
    domain: str | None
    reason: str | None
    source: str | None
    created_at: datetime


class SuppressionListResponse(BaseModel):
    items: list[SuppressionRead]
    total: int
    skip: int
    limit: int
