from pydantic import BaseModel, ConfigDict, Field


class UserSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sender_name: str | None = None
    sender_company: str | None = None
    business_address: str | None = None


class UserSettingsUpdate(BaseModel):
    sender_name: str | None = Field(default=None, max_length=255)
    sender_company: str | None = Field(default=None, max_length=255)
    business_address: str | None = Field(default=None, max_length=500)
