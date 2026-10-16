"""Plan limits. Plans live in code; per-workspace overrides live in ``workspaces.plan_overrides``."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any

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
    monthly_verifications: int = 0

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
        monthly_verifications=100,
    ),
    "starter": PlanLimits(
        monthly_sends=5_000,
        monthly_leads=10_000,
        seats=5,
        monthly_llm_tokens=2_000_000,
        daily_enrichments=300,
        daily_hunter_lookups=200,
        max_campaigns=20,
        monthly_verifications=2_000,
    ),
    "pro": PlanLimits(
        monthly_sends=50_000,
        monthly_leads=100_000,
        seats=20,
        monthly_llm_tokens=10_000_000,
        daily_enrichments=2_000,
        daily_hunter_lookups=1_000,
        max_campaigns=100,
        monthly_verifications=20_000,
    ),
    "enterprise": PlanLimits(
        monthly_sends=250_000,
        monthly_leads=1_000_000,
        seats=200,
        monthly_llm_tokens=50_000_000,
        daily_enrichments=10_000,
        daily_hunter_lookups=5_000,
        max_campaigns=1_000,
        monthly_verifications=100_000,
    ),
}


@dataclass(frozen=True)
class PlanFeatures:
    """What a plan includes, as opposed to how much (PlanLimits)."""

    sso: bool = False  # sign in with the workspace's own OIDC identity provider
    saml: bool = False  # SAML 2.0 identity providers
    custom_roles: bool = False
    api_access: bool = False
    integrations: bool = False  # HubSpot and Pipedrive sync
    audit_log_retention_days: int = 30

    def as_dict(self) -> dict[str, bool | int]:
        return asdict(self)


PLAN_FEATURES: dict[str, PlanFeatures] = {
    "free": PlanFeatures(),
    "starter": PlanFeatures(api_access=True, audit_log_retention_days=90),
    "pro": PlanFeatures(sso=True, api_access=True, integrations=True, audit_log_retention_days=365),
    "enterprise": PlanFeatures(
        sso=True,
        saml=True,
        custom_roles=True,
        api_access=True,
        integrations=True,
        audit_log_retention_days=730,
    ),
}


def features_for(workspace: Workspace) -> PlanFeatures:
    base = PLAN_FEATURES.get(workspace.plan, PLAN_FEATURES["free"])
    raw = (workspace.plan_overrides or {}).get("features") or {}
    known = base.as_dict()
    overrides: dict[str, Any] = {
        key: (bool(value) if isinstance(known[key], bool) else int(value))
        for key, value in raw.items()
        if key in known
    }
    return replace(base, **overrides) if overrides else base


def require_feature(workspace: Workspace, feature: str, label: str) -> None:
    from app.core.errors import PermissionDeniedError

    if not getattr(features_for(workspace), feature):
        raise PermissionDeniedError(
            f"{label} isn't included in your plan. Upgrade to use it.",
            extra={"code": "plan_feature_required", "feature": feature},
        )


# Which counter period each metric uses.
METRIC_PERIOD = {
    "monthly_sends": "month",
    "monthly_leads": "month",
    "monthly_llm_tokens": "month",
    "monthly_verifications": "month",
    "daily_enrichments": "day",
    "daily_hunter_lookups": "day",
}


def limits_for(workspace: Workspace) -> PlanLimits:
    base = PLANS.get(workspace.plan, PLANS["free"])
    overrides = {
        key: int(value)
        for key, value in (workspace.plan_overrides or {}).items()
        if key in base.as_dict() and not isinstance(value, dict)
    }
    return replace(base, **overrides) if overrides else base
