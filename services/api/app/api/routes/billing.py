from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_workspace, require_permission
from app.core.database import get_db
from app.core.permissions import Permission
from app.core.tenancy import WorkspaceContext
from app.models.billing import Subscription
from app.models.user import User
from app.services.billing import credits as credit_service
from app.services.billing import stripe_billing
from app.services.billing.plans import METRIC_PERIOD, PLANS, features_for, limits_for
from app.services.billing.provider import BillingNotConfiguredError
from app.services.billing.stripe_client import SignatureError, StripeError
from app.services.billing.usage import current_usage

router = APIRouter(prefix="/billing", tags=["billing"])


class UsageItem(BaseModel):
    metric: str
    used: int
    limit: int
    period: str


class SubscriptionInfo(BaseModel):
    status: str | None
    plan: str | None
    interval: str | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    past_due_since: datetime | None
    grace_ends_at: datetime | None
    has_billing_account: bool


class CreditPackInfo(BaseModel):
    credits: int
    amount: float | None
    purchasable: bool


class CreditsInfo(BaseModel):
    balance: int
    packs: list[CreditPackInfo]
    # How many units of each metric one credit buys, e.g. {"monthly_llm_tokens": 1000}.
    units: dict[str, int]


class CreditTransactionRead(BaseModel):
    id: int
    amount: int
    kind: str
    metric: str | None
    note: str | None
    balance_after: int
    created_at: datetime


class CreditCheckoutRequest(BaseModel):
    credits: int = Field(gt=0, le=10_000_000)


class BillingSummary(BaseModel):
    plan: str
    limits: dict[str, int]
    features: dict[str, bool | int] = {}
    usage: list[UsageItem]
    billing_enabled: bool = False
    # "plan:interval" options that can be bought online, e.g. ["starter:month", "pro:year"]
    purchasable: list[str] = []
    plan_limits: dict[str, dict[str, int]] = {}
    trial_ends_at: datetime | None = None
    subscription: SubscriptionInfo | None = None
    sending_paused_for_payment: bool = False
    credits: CreditsInfo | None = None


def credits_info(db: Session, workspace_id: int) -> CreditsInfo:
    online = stripe_billing.billing_enabled()
    return CreditsInfo(
        balance=credit_service.balance(db, workspace_id),
        packs=[
            CreditPackInfo(**credit_service.pack_payload(pack, online))
            for pack in credit_service.credit_packs()
        ],
        units=dict(credit_service.CREDIT_UNITS),
    )


class CheckoutRequest(BaseModel):
    plan: str
    interval: Literal["month", "year"] = "month"


class UrlResponse(BaseModel):
    url: str


class Invoice(BaseModel):
    id: str | None
    number: str | None
    status: str | None
    amount_due: int
    amount_paid: int
    currency: str
    created: datetime | None
    hosted_invoice_url: str | None
    invoice_pdf: str | None


def _require_billing() -> None:
    if not stripe_billing.billing_enabled():
        raise BillingNotConfiguredError(
            "Online billing isn't available yet. Contact support to upgrade."
        )


@router.get("", response_model=BillingSummary)
def get_billing(
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> BillingSummary:
    workspace = ctx.workspace
    limits = limits_for(workspace)
    row = db.scalar(select(Subscription).where(Subscription.workspace_id == ctx.workspace_id))
    return BillingSummary(
        plan=workspace.plan,
        limits=limits.as_dict(),
        features=features_for(workspace).as_dict(),
        usage=[
            UsageItem(
                metric=metric,
                used=current_usage(db, ctx.workspace_id, metric),
                limit=getattr(limits, metric),
                period=period,
            )
            for metric, period in METRIC_PERIOD.items()
        ],
        billing_enabled=stripe_billing.billing_enabled(),
        purchasable=sorted(stripe_billing.prices()) if stripe_billing.billing_enabled() else [],
        plan_limits={name: plan.as_dict() for name, plan in PLANS.items()},
        trial_ends_at=workspace.trial_ends_at,
        subscription=SubscriptionInfo(
            status=row.status,
            plan=row.plan,
            interval=row.interval,
            current_period_end=row.current_period_end,
            cancel_at_period_end=row.cancel_at_period_end,
            past_due_since=row.past_due_since,
            grace_ends_at=stripe_billing.grace_ends_at(row),
            has_billing_account=bool(row.stripe_customer_id),
        )
        if row
        else None,
        sending_paused_for_payment=bool(
            workspace.sending_suspended_at
            and (workspace.sending_suspended_reason or "").startswith(stripe_billing.DUNNING_REASON)
        ),
        credits=credits_info(db, ctx.workspace_id),
    )


@router.post("/checkout", response_model=UrlResponse)
def create_checkout(
    payload: CheckoutRequest,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.BILLING_MANAGE)),
) -> UrlResponse:
    _require_billing()
    try:
        return UrlResponse(
            url=stripe_billing.create_checkout(
                db, ctx.workspace, user, payload.plan, payload.interval
            )
        )
    except StripeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/credits/checkout", response_model=UrlResponse)
def create_credit_checkout(
    payload: CreditCheckoutRequest,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.BILLING_MANAGE)),
) -> UrlResponse:
    """Buy a credit pack (a one-off payment). Credits are added when Stripe confirms payment."""
    _require_billing()
    try:
        return UrlResponse(
            url=stripe_billing.create_credit_checkout(db, ctx.workspace, user, payload.credits)
        )
    except StripeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/credits", response_model=list[CreditTransactionRead])
def credit_history(
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[Any]:
    """The latest 50 credit purchases, grants and daily usage."""
    return credit_service.history(db, ctx.workspace_id)


@router.post("/portal", response_model=UrlResponse)
def create_portal(
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.BILLING_MANAGE)),
) -> UrlResponse:
    """Stripe's customer portal: card details, invoices, plan changes and cancellation."""
    _require_billing()
    try:
        return UrlResponse(url=stripe_billing.create_portal(db, ctx.workspace))
    except StripeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/invoices", response_model=list[Invoice])
def list_invoices(
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.BILLING_MANAGE)),
) -> list[Any]:
    if not stripe_billing.billing_enabled():
        return []
    try:
        return stripe_billing.list_invoices(db, ctx.workspace)
    except StripeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/webhooks/stripe", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not stripe_billing.billing_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    payload = await request.body()
    if len(payload) > 1_000_000:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Too large"
        )
    try:
        result = stripe_billing.handle_webhook(db, payload, stripe_signature)
    except SignatureError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except StripeError as exc:
        # Stripe retries non-2xx responses, which is what we want if its API was unreachable.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return {"result": result}
