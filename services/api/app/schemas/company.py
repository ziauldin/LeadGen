from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EnrichmentStatus


class CompanyBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    website: str | None = Field(default=None, max_length=500)
    domain: str | None = Field(default=None, max_length=255)
    industry: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=100)
    size_estimate: int | None = Field(default=None, ge=0)
    contact_page_url: str | None = Field(default=None, max_length=500)
    about_page_url: str | None = Field(default=None, max_length=500)


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    website: str | None = Field(default=None, max_length=500)
    domain: str | None = Field(default=None, max_length=255)
    industry: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=100)
    size_estimate: int | None = Field(default=None, ge=0)
    contact_page_url: str | None = Field(default=None, max_length=500)
    about_page_url: str | None = Field(default=None, max_length=500)


class CompanyRead(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    robots_checked: bool
    enrichment_status: EnrichmentStatus
    enrichment_message: str | None = None
    created_at: datetime
    updated_at: datetime


class CompanyListResponse(BaseModel):
    items: list[CompanyRead]
    total: int
    skip: int
    limit: int


class EnrichCompanyResponse(BaseModel):
    company_id: int
    status: str
    message: str
