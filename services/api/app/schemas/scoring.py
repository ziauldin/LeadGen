from pydantic import BaseModel, Field

from app.models.enums import LeadStatus


class ScoringRuleRead(BaseModel):
    key: str
    label: str
    points: int
    description: str


class ScoreBreakdownRead(BaseModel):
    rule_key: str
    label: str
    points: int
    reason: str


class LeadScoreRead(BaseModel):
    lead_id: int
    total: float
    breakdown: list[ScoreBreakdownRead]
    suggested_status: LeadStatus
    applied_status: LeadStatus


class RecalculateRequest(BaseModel):
    niche_id: int | None = None
    lead_ids: list[int] = Field(default_factory=list)


class RecalculateResponse(BaseModel):
    updated: int
    results: list[LeadScoreRead]
