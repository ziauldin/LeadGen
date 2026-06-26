from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EmailPreviewRequest(BaseModel):
    lead_id: int
    template_id: str = Field(default="wellpredict")


class EmailGenerateRequest(BaseModel):
    lead_id: int
    template_id: str = Field(default="wellpredict")
    campaign_id: int | None = None


class EmailApproveRequest(BaseModel):
    email_message_id: int


class EmailTemplateRead(BaseModel):
    id: str
    name: str
    subject: str


class EmailPreviewResponse(BaseModel):
    lead_id: int
    template_id: str
    recipient_email: str
    subject: str
    body: str
    variables: dict[str, str]
    has_opt_out_line: bool
    compliance_errors: list[str]
    can_send: bool


class EmailMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    campaign_id: int | None
    recipient_email: str
    subject: str
    body: str
    status: str
    unsubscribe_token: str | None
    sent_at: datetime | None


class EmailGenerateResponse(BaseModel):
    message: EmailMessageRead
    compliance_errors: list[str]


class EmailApproveResponse(BaseModel):
    message: EmailMessageRead
