from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CampaignStatus


class CampaignStepBase(BaseModel):
    step_number: int = Field(ge=1)
    delay_days: int = Field(default=0, ge=0)
    subject_template: str = Field(min_length=1, max_length=500)
    body_template: str = Field(min_length=1)


class CampaignStepRead(CampaignStepBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int


class CampaignCreate(BaseModel):
    niche_id: int
    name: str = Field(min_length=1, max_length=255)
    daily_send_limit: int | None = Field(default=None, ge=1)
    sending_window_start: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    sending_window_end: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    steps: list[CampaignStepBase] = Field(default_factory=list)


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    daily_send_limit: int | None = Field(default=None, ge=1)
    sending_window_start: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    sending_window_end: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    status: CampaignStatus | None = None


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    niche_id: int
    name: str
    status: CampaignStatus
    daily_send_limit: int
    sending_window_start: str | None
    sending_window_end: str | None
    created_at: datetime
    steps: list[CampaignStepRead] = Field(default_factory=list)


class CampaignListResponse(BaseModel):
    items: list[CampaignRead]
    total: int
    skip: int
    limit: int


class AddLeadsRequest(BaseModel):
    lead_ids: list[int] = Field(min_length=1)


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
