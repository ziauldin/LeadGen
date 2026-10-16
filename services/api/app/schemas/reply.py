from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReplyClassification


class ReplyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email_message_id: int | None
    from_email: str
    subject: str | None = None
    body: str
    snippet: str = ""
    classification: ReplyClassification
    classified_by: str | None = None
    classification_confidence: float | None = None
    is_auto_reply: bool = False
    match_method: str | None = None
    received_at: datetime
    lead_id: int | None = None
    lead_name: str | None = None
    campaign_id: int | None = None
    notes: str | None = None


class SentMessageSummary(BaseModel):
    id: int
    subject: str
    body: str
    sent_at: datetime | None
    step_number: int | None


class ReplyDetail(ReplyRead):
    raw_body: str | None = None
    in_reply_to: str | None = None
    thread: list[SentMessageSummary] = Field(default_factory=list)


class ReplyListResponse(BaseModel):
    items: list[ReplyRead]
    total: int
    skip: int
    limit: int


class ReplyUpdate(BaseModel):
    classification: ReplyClassification | None = None
    mark_meeting_booked: bool = False
    notes: str | None = Field(default=None, max_length=5000)


class ReplyLinkRequest(BaseModel):
    email_message_id: int


class ReplySyncResponse(BaseModel):
    synced: int
    message: str
