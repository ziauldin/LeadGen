from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AIMode = Literal["off", "assist"]


class UserSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sender_name: str | None = None
    sender_company: str | None = None
    business_address: str | None = None
    product_description: str | None = None
    tone_guidelines: str | None = None
    ai_mode: str = "off"
    block_risky_emails: bool = False


class UserSettingsUpdate(BaseModel):
    sender_name: str | None = Field(default=None, max_length=255)
    sender_company: str | None = Field(default=None, max_length=255)
    business_address: str | None = Field(default=None, max_length=500)
    # What the sender offers, in their words; AI drafts may only use facts from here.
    product_description: str | None = Field(default=None, max_length=2000)
    tone_guidelines: str | None = Field(default=None, max_length=1000)
    # "assist": AI drafts and reply labelling are available on request; "off": templates only.
    ai_mode: AIMode | None = None
    block_risky_emails: bool | None = None


class DeliverabilityCheck(BaseModel):
    name: str
    status: Literal["pass", "warn", "fail", "unknown"]
    detail: str
    records: list[str] = []


class DeliverabilityReport(BaseModel):
    domain: str
    provider: str | None
    overall: Literal["pass", "warn", "fail"]
    checks: list[DeliverabilityCheck]
