from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NicheBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    country: str = Field(min_length=1, max_length=100)
    industry: str = Field(min_length=1, max_length=255)
    target_roles: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    exclusion_keywords: list[str] = Field(default_factory=list)
    company_size_min: int | None = Field(default=None, ge=0)
    company_size_max: int | None = Field(default=None, ge=0)


class NicheCreate(NicheBase):
    pass


class NicheUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    country: str | None = Field(default=None, min_length=1, max_length=100)
    industry: str | None = Field(default=None, min_length=1, max_length=255)
    target_roles: list[str] | None = None
    keywords: list[str] | None = None
    exclusion_keywords: list[str] | None = None
    company_size_min: int | None = Field(default=None, ge=0)
    company_size_max: int | None = Field(default=None, ge=0)


class NicheRead(NicheBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime


class NicheListResponse(BaseModel):
    items: list[NicheRead]
    total: int
    skip: int
    limit: int
