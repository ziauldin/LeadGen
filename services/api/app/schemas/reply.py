from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReplyClassification


class ReplyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email_message_id: int
    from_email: str
    body: str
    classification: ReplyClassification
    received_at: datetime
    lead_id: int | None = None
    lead_name: str | None = None
    campaign_id: int | None = None
    notes: str | None = None


class ReplyListResponse(BaseModel):
    items: list[ReplyRead]
    total: int
    skip: int
    limit: int


class ReplyUpdate(BaseModel):
    classification: ReplyClassification | None = None
    mark_meeting_booked: bool = False
    notes: str | None = None


class ReplySyncResponse(BaseModel):
    synced: int
    message: str
