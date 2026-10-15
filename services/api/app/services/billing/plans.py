"""Plan limits. Plans live in code; per-workspace overrides live in ``workspaces.plan_overrides``."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from app.models.workspace import Workspace


@dataclass(frozen=True)
class PlanLimits:
    monthly_sends: int
    monthly_leads: int
    seats: int
    monthly_llm_tokens: int
    daily_enrichments: int
    daily_hunter_lookups: int
    max_campaigns: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


PLANS: dict[str, PlanLimits] = {
    "free": PlanLimits(
        monthly_sends=500,
        monthly_leads=1_000,
        seats=2,
        monthly_llm_tokens=200_000,
        daily_enrichments=50,
        daily_hunter_lookups=25,
        max_campaigns=3,
    ),
    "starter": PlanLimits(
        monthly_sends=5_000,
        monthly_leads=10_000,
        seats=5,
        monthly_llm_tokens=2_000_000,
        daily_enrichments=300,
        daily_hunter_lookups=200,
        max_campaigns=20,
    ),
    "pro": PlanLimits(
        monthly_sends=50_000,
        monthly_leads=100_000,
        seats=20,
        monthly_llm_tokens=10_000_000,
        daily_enrichments=2_000,
        daily_hunter_lookups=1_000,
        max_campaigns=100,
    ),
}

# Which counter period each metric uses.
METRIC_PERIOD = {
    "monthly_sends": "month",
    "monthly_leads": "month",
    "monthly_llm_tokens": "month",
    "daily_enrichments": "day",
    "daily_hunter_lookups": "day",
}


def limits_for(workspace: Workspace) -> PlanLimits:
    base = PLANS.get(workspace.plan, PLANS["free"])
    overrides = {
        key: int(value)
        for key, value in (workspace.plan_overrides or {}).items()
        if key in base.as_dict()
    }
    return replace(base, **overrides) if overrides else base
