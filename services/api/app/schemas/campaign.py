from datetime import datetime
from typing import Literal
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import CampaignStatus
from app.schemas.common import BulkItemResult

_TIMEZONES = available_timezones()
_HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


def _check_timezone(value: str | None) -> str | None:
    if value is not None and value not in _TIMEZONES:
        raise ValueError("Unknown timezone")
    return value


def _check_days(value: list[int] | None) -> list[int] | None:
    if value is None:
        return None
    days = sorted(set(value))
    if not days or any(day < 0 or day > 6 for day in days):
        raise ValueError("Sending days must be weekday numbers 0 (Monday) to 6 (Sunday)")
    return days


class StepVariant(BaseModel):
    key: Literal["B", "C", "D"]
    subject_template: str = Field(min_length=1, max_length=500)
    body_template: str = Field(min_length=1, max_length=20_000)


class CampaignStepBase(BaseModel):
    step_number: int = Field(ge=1, le=20)
    delay_days: int = Field(default=0, ge=0, le=365)
    # Either a saved template (copied into the step) or the step's own subject and body.
    template_id: str | None = Field(default=None, max_length=100)
    subject_template: str | None = Field(default=None, min_length=1, max_length=500)
    body_template: str | None = Field(default=None, min_length=1, max_length=20_000)
    # Draft this step with AI (the template is the fallback). People still approve every email.
    use_ai: bool = False
    ai_instructions: str | None = Field(default=None, max_length=2000)
    thread_with_previous: bool = True
    # A/B test: up to three extra versions, split evenly with the main one (A).
    variants: list[StepVariant] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def needs_content(self) -> "CampaignStepBase":
        keys = [v.key for v in self.variants]
        if len(keys) != len(set(keys)):
            raise ValueError("Each A/B version needs its own letter")
        if not self.template_id and not (self.subject_template and self.body_template):
            raise ValueError("Give a template_id, or both subject_template and body_template")
        return self


class CampaignStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    step_number: int
    delay_days: int
    template_id: str | None
    subject_template: str
    body_template: str
    use_ai: bool
    ai_instructions: str | None
    thread_with_previous: bool
    variants: list[StepVariant] = []

    @field_validator("variants", mode="before")
    @classmethod
    def no_variants(cls, value: object) -> object:
        return value or []


class CampaignScheduleFields(BaseModel):
    timezone: str | None = Field(default=None, max_length=64)
    sending_days: list[int] | None = None
    per_domain_limit: int | None = Field(default=None, ge=1, le=1000)
    sender_credential_id: int | None = None
    stop_on_reply: bool | None = None

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str | None) -> str | None:
        return _check_timezone(value)

    @field_validator("sending_days")
    @classmethod
    def valid_days(cls, value: list[int] | None) -> list[int] | None:
        return _check_days(value)


class CampaignCreate(CampaignScheduleFields):
    niche_id: int
    name: str = Field(min_length=1, max_length=255)
    daily_send_limit: int | None = Field(default=None, ge=1, le=10_000)
    sending_window_start: str | None = Field(default=None, pattern=_HHMM)
    sending_window_end: str | None = Field(default=None, pattern=_HHMM)
    steps: list[CampaignStepBase] = Field(default_factory=list, max_length=20)


class CampaignUpdate(CampaignScheduleFields):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    daily_send_limit: int | None = Field(default=None, ge=1, le=10_000)
    sending_window_start: str | None = Field(default=None, pattern=_HHMM)
    sending_window_end: str | None = Field(default=None, pattern=_HHMM)
    # The full list of steps. Edits apply to drafts created from now on.
    steps: list[CampaignStepBase] | None = Field(default=None, min_length=1, max_length=20)

    @field_validator("steps")
    @classmethod
    def unique_step_numbers(
        cls, value: list[CampaignStepBase] | None
    ) -> list[CampaignStepBase] | None:
        if value is not None and len({s.step_number for s in value}) != len(value):
            raise ValueError("Step numbers must be unique")
        return value


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    niche_id: int
    name: str
    status: CampaignStatus
    daily_send_limit: int
    sending_window_start: str | None
    sending_window_end: str | None
    timezone: str | None = None
    sending_days: list[int] | None = None
    per_domain_limit: int | None = None
    sender_credential_id: int | None = None
    stop_on_reply: bool = True
    auto_paused_reason: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    steps: list[CampaignStepRead] = Field(default_factory=list)


class CampaignStepMetrics(BaseModel):
    step_number: int
    drafts: int
    awaiting_approval: int
    sent: int
    bounced: int
    replies: int
    reply_rate: float


class CampaignMetrics(BaseModel):
    campaign_id: int
    status: str
    enrolled: int
    enrollments_by_status: dict[str, int]
    messages_by_status: dict[str, int]
    awaiting_approval: int
    scheduled: int
    sent: int
    bounced: int
    complained: int
    replies: int
    positive_replies: int
    replies_by_classification: dict[str, int]
    reply_rate: float
    positive_rate: float
    bounce_rate: float
    complaint_rate: float
    steps: list[CampaignStepMetrics]


class CampaignMessageRead(BaseModel):
    id: int
    lead_id: int
    lead_name: str | None
    recipient_email: str
    subject: str
    status: str
    step_number: int | None
    scheduled_for: datetime | None
    sent_at: datetime | None
    failure_reason: str | None
    reply_status: str | None
    generation_mode: str | None


class CampaignMessageList(BaseModel):
    items: list[CampaignMessageRead]
    total: int
    skip: int
    limit: int


class CampaignListResponse(BaseModel):
    items: list[CampaignRead]
    total: int
    skip: int
    limit: int


class AddLeadsRequest(BaseModel):
    lead_ids: list[int] = Field(min_length=1, max_length=500)


class AddLeadsResponse(BaseModel):
    created: int
    skipped: int
    errors: list[str]
    message_ids: list[int] = Field(default_factory=list)
    results: list[BulkItemResult] = Field(default_factory=list)


class CampaignActionResponse(BaseModel):
    campaign: CampaignRead
    message: str


class EnrollmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    lead_id: int
    lead_name: str | None = None
    recipient_email: str
    status: str
    current_step: int
    next_step_number: int | None
    next_send_at: datetime | None
    last_sent_at: datetime | None
    stopped_reason: str | None
    created_at: datetime


class EnrollmentListResponse(BaseModel):
    items: list[EnrollmentRead]
    total: int
    skip: int
    limit: int


class ProcessSendsResponse(BaseModel):
    sent: int
    failed: int
    skipped: int
