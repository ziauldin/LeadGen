from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace, require_owner
from app.core.database import get_db
from app.core.tenancy import WorkspaceContext
from app.services.billing.plans import METRIC_PERIOD, limits_for
from app.services.billing.provider import get_billing_provider
from app.services.billing.usage import current_usage

router = APIRouter(prefix="/billing", tags=["billing"])


class UsageItem(BaseModel):
    metric: str
    used: int
    limit: int
    period: str


class BillingSummary(BaseModel):
    plan: str
    limits: dict[str, int]
    usage: list[UsageItem]


class CheckoutRequest(BaseModel):
    plan: str


@router.get("", response_model=BillingSummary)
def get_billing(
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> BillingSummary:
    limits = limits_for(ctx.workspace)
    return BillingSummary(
        plan=ctx.workspace.plan,
        limits=limits.as_dict(),
        usage=[
            UsageItem(
                metric=metric,
                used=current_usage(db, ctx.workspace_id, metric),
                limit=getattr(limits, metric),
                period=period,
            )
            for metric, period in METRIC_PERIOD.items()
        ],
    )


@router.post("/checkout")
def create_checkout(
    payload: CheckoutRequest,
    ctx: WorkspaceContext = Depends(require_owner),
) -> dict[str, str]:
    url = get_billing_provider().create_checkout(ctx.workspace, payload.plan)
    return {"url": url}
