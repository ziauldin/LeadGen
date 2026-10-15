from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GenerationMode = Literal["template", "ai"]


class EmailPreviewRequest(BaseModel):
    lead_id: int
    template_id: str = Field(default="system:intro", max_length=100)
    mode: GenerationMode = "template"
    instructions: str | None = Field(default=None, max_length=2000)


class EmailGenerateRequest(BaseModel):
    lead_id: int
    template_id: str = Field(default="system:intro", max_length=100)
    campaign_id: int | None = None
    mode: GenerationMode = "template"
    instructions: str | None = Field(default=None, max_length=2000)


class EmailRegenerateRequest(BaseModel):
    mode: GenerationMode = "template"
    template_id: str | None = Field(default=None, max_length=100)
    instructions: str | None = Field(default=None, max_length=2000)


class EmailApproveRequest(BaseModel):
    email_message_id: int


class EmailTemplateRead(BaseModel):
    id: str
    name: str
    subject: str
    description: str = ""
    is_system: bool = True


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
    generation_mode: str = "template"
    llm_model: str | None = None
    generation_note: str | None = None


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
    step_number: int | None = None
    generation_mode: str | None = None
    template_id: str | None = None
    llm_model: str | None = None
    generation_note: str | None = None


class EmailGenerateResponse(BaseModel):
    message: EmailMessageRead
    compliance_errors: list[str]


class EmailApproveResponse(BaseModel):
    message: EmailMessageRead
