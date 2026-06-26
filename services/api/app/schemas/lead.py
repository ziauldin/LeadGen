from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EnrichmentStatus, LeadStatus


class CompanySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    website: str | None = None
    domain: str | None = None


class LeadBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    job_title: str | None = Field(default=None, max_length=255)
    linkedin_url: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=500)
    source_provider: str | None = Field(default=None, max_length=100)
    company_id: int | None = None
    status: LeadStatus = LeadStatus.NEW
    score: float = Field(default=0.0, ge=0)
    qualification_notes: str | None = None
    compliance_source_note: str | None = None


class LeadCreate(LeadBase):
    niche_id: int


class LeadUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    job_title: str | None = Field(default=None, max_length=255)
    linkedin_url: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=500)
    source_provider: str | None = Field(default=None, max_length=100)
    company_id: int | None = None
    status: LeadStatus | None = None
    score: float | None = Field(default=None, ge=0)
    qualification_notes: str | None = None
    compliance_source_note: str | None = None


class LeadRead(LeadBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    niche_id: int
    created_at: datetime
    updated_at: datetime
    company: CompanySummary | None = None
    primary_email: str | None = None


class LeadListResponse(BaseModel):
    items: list[LeadRead]
    total: int
    skip: int
    limit: int


class LeadImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[str]
