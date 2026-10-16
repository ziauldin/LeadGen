"""Analytics: daily series and breakdowns, A/B variant results, CSV export."""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace, require_permission
from app.core.database import get_db
from app.core.flags import feature_enabled
from app.core.permissions import Permission
from app.core.tenancy import WorkspaceContext
from app.services.analytics import service as analytics
from app.services.campaigns.service import get_campaign

router = APIRouter(tags=["analytics"])


class Counts(BaseModel):
    sent: int
    bounced: int
    replies: int
    positive: int
    reply_rate: float
    positive_rate: float
    bounce_rate: float


class SeriesPoint(BaseModel):
    date: str
    sent: int
    bounced: int
    replies: int
    positive: int


class BreakdownRow(Counts):
    key: Any
    label: str


class Overview(BaseModel):
    days: int
    totals: Counts
    series: list[SeriesPoint]
    by_campaign: list[BreakdownRow]
    by_step: list[BreakdownRow]
    by_variant: list[BreakdownRow]
    by_mailbox: list[BreakdownRow]
    by_template: list[BreakdownRow]


class VariantStats(BaseModel):
    variant: str
    sent: int
    bounced: int
    replies: int
    positive: int
    reply_rate: float
    positive_rate: float
    bounce_rate: float


class Winner(BaseModel):
    variant: str
    p_value: float


class StepVariants(BaseModel):
    step_number: int
    variants: list[VariantStats]
    winner: Winner | None
    min_sends: int


def _enabled(ctx: WorkspaceContext = Depends(get_current_workspace)) -> WorkspaceContext:
    if not feature_enabled("analytics_v2", ctx.workspace):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analytics isn't enabled")
    return ctx


@router.get("/analytics/overview", response_model=Overview)
def get_overview(
    days: int = Query(default=30, ge=1, le=365),
    campaign_id: int | None = None,
    ctx: WorkspaceContext = Depends(_enabled),
    db: Session = Depends(get_db),
) -> Overview:
    if campaign_id is not None:
        get_campaign(db, campaign_id, ctx.workspace_id)
    return Overview(**analytics.overview(db, ctx.workspace_id, days=days, campaign_id=campaign_id))


@router.get("/analytics/export")
def export(
    days: int = Query(default=30, ge=1, le=365),
    ctx: WorkspaceContext = Depends(_enabled),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.DATA_EXPORT)),
) -> StreamingResponse:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["date", "sent", "bounced", "replies", "positive"])
    writer.writeheader()
    writer.writerows(analytics.export_rows(db, ctx.workspace_id, days=days))
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="leadsgen-analytics-{days}d.csv"'},
    )


@router.get("/campaigns/{campaign_id}/variants", response_model=list[StepVariants])
def campaign_variants(
    campaign_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[StepVariants]:
    get_campaign(db, campaign_id, ctx.workspace_id)
    return [
        StepVariants(**row) for row in analytics.variant_results(db, ctx.workspace_id, campaign_id)
    ]
