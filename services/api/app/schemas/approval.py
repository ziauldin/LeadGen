from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import MAX_BULK


class ApprovalLead(BaseModel):
    id: int
    full_name: str
    job_title: str | None
    company_name: str | None
    company_domain: str | None
    score: float
    status: str


class ApprovalItem(BaseModel):
    id: int
    status: str
    recipient_email: str
    subject: str
    body: str
    step_number: int | None
    scheduled_for: datetime | None
    created_at: datetime
    campaign_id: int | None
    campaign_name: str | None
    lead: ApprovalLead | None
    generation_mode: str | None
    generation_note: str | None
    llm_model: str | None
    template_id: str | None
    edited_at: datetime | None
    problems: list[str]
    can_approve: bool


class ApprovalQueue(BaseModel):
    items: list[ApprovalItem]
    total: int
    skip: int
    limit: int
    by_campaign: dict[str, int]


class BulkApproveRequest(BaseModel):
    message_ids: list[int] = Field(min_length=1, max_length=MAX_BULK)


class BulkRejectRequest(BaseModel):
    message_ids: list[int] = Field(min_length=1, max_length=MAX_BULK)
    reason: str | None = Field(default=None, max_length=500)


class EmailEditRequest(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=500)
    body: str | None = Field(default=None, min_length=1, max_length=20_000)


class EmailRejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
