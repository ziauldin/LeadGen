from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import LeadStatus
from app.schemas.common import MAX_BULK


class CompanySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    website: str | None = None
    domain: str | None = None
    enrichment_status: str | None = None


class LeadBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    job_title: str | None = Field(default=None, max_length=255)
    linkedin_url: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=500)
    source_provider: str | None = Field(default=None, max_length=100)
    company_id: int | None = None
    qualification_notes: str | None = Field(default=None, max_length=5000)
    compliance_source_note: str | None = Field(default=None, max_length=2000)


class LeadCreate(LeadBase):
    niche_id: int
    status: LeadStatus = LeadStatus.NEW


class LeadUpdate(BaseModel):
    """Score is calculated by the scoring rules and cannot be set by clients."""

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    job_title: str | None = Field(default=None, max_length=255)
    linkedin_url: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=500)
    source_provider: str | None = Field(default=None, max_length=100)
    company_id: int | None = None
    status: LeadStatus | None = None
    qualification_notes: str | None = Field(default=None, max_length=5000)
    compliance_source_note: str | None = Field(default=None, max_length=2000)


class EmailContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    email_type: str | None = None
    confidence: float = 0.0
    source_url: str | None = None
    source_provider: str | None = None
    is_role_based: bool = False
    opted_out: bool
    created_at: datetime


class LeadRead(LeadBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    niche_id: int
    status: LeadStatus
    score: float
    created_at: datetime
    updated_at: datetime
    company: CompanySummary | None = None
    primary_email: str | None = None
    email_contacts: list[EmailContactRead] = []


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


BulkLeadAction = Literal["add_to_campaign", "enrich", "set_status", "delete", "rescore"]


class LeadBulkRequest(BaseModel):
    lead_ids: list[int] = Field(min_length=1, max_length=MAX_BULK)
    action: BulkLeadAction
    campaign_id: int | None = None
    status: LeadStatus | None = None

    @model_validator(mode="after")
    def needs_target(self) -> "LeadBulkRequest":
        if self.action == "add_to_campaign" and self.campaign_id is None:
            raise ValueError("campaign_id is required to add leads to a campaign")
        if self.action == "set_status" and self.status is None:
            raise ValueError("status is required to change lead status")
        return self


class LeadStats(BaseModel):
    total: int
    by_status: dict[str, int]
    with_email: int
    without_email: int
    average_score: float
    added_last_7_days: int
    in_active_sequences: int
