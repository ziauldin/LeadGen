from datetime import datetime
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import CampaignStatus

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


class CampaignStepBase(BaseModel):
    step_number: int = Field(ge=1, le=20)
    delay_days: int = Field(default=0, ge=0, le=365)
    subject_template: str = Field(min_length=1, max_length=500)
    body_template: str = Field(min_length=1, max_length=20_000)


class CampaignStepRead(CampaignStepBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int


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


class CampaignActionResponse(BaseModel):
    campaign: CampaignRead
    message: str


class ProcessSendsResponse(BaseModel):
    sent: int
    failed: int
    skipped: int
