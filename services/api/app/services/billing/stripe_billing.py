"""Stripe-backed plans: checkout, customer portal, webhooks, trials and dunning.

Stripe is the source of truth. Each webhook event is stored once, then the subscription is
re-read from the Stripe API and reconciled, so events arriving out of order or twice are safe.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ValidationFailedError
from app.core.tenancy import system_session, workspace_scope
from app.models.billing import BillingEvent, Subscription
from app.models.user import User
from app.models.workspace import Workspace
from app.services.billing.plans import PLANS
from app.services.billing.stripe_client import StripeClient, verify_signature
from app.services.notifications import events as notify_events
from app.services.workspaces.service import audit

logger = logging.getLogger(__name__)

PAID_STATUSES = {"active", "trialing"}
ENDED_STATUSES = {"canceled", "unpaid", "incomplete_expired"}
DUNNING_REASON = "Payment overdue"
HANDLED_EVENTS = {
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
}


def billing_enabled() -> bool:
    return settings.feature_billing and bool(settings.stripe_secret_key)


@lru_cache
def _price_table(raw: str) -> dict[str, str]:
    try:
        table = json.loads(raw or "{}")
    except json.JSONDecodeError:
        logger.error("STRIPE_PRICES is not valid JSON")
        return {}
    return {str(k): str(v) for k, v in table.items()}


def prices() -> dict[str, str]:
    """``{"starter:month": "price_..."}`` for the plans that can be bought online."""
    return {
        k: v for k, v in _price_table(settings.stripe_prices).items() if k.split(":")[0] in PLANS
    }


def plan_for_price(price_id: str) -> tuple[str | None, str | None]:
    for key, value in prices().items():
        if value == price_id:
            plan, _, interval = key.partition(":")
            return plan, interval or None
    return None, None


def _ts(value: Any) -> datetime | None:
    return datetime.fromtimestamp(int(value), UTC) if value else None


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def subscription_row(db: Session, workspace_id: int) -> Subscription:
    row = db.scalar(select(Subscription).where(Subscription.workspace_id == workspace_id))
    if row is None:
        row = Subscription(workspace_id=workspace_id)
        db.add(row)
        db.flush()
    return row


# --- trials --------------------------------------------------------------------------------------


def start_trial(workspace: Workspace) -> None:
    """New personal workspaces try the Starter plan for free (FEATURE_BILLING only)."""
    if not settings.feature_billing or settings.billing_trial_days <= 0 or "starter" not in PLANS:
        return
    workspace.plan = "starter"
    workspace.trial_ends_at = _now() + timedelta(days=settings.billing_trial_days)


def expire_trials(db: Session) -> int:
    """Daily: trials that ended without a paid subscription go back to Free."""
    expired = 0
    for workspace in db.scalars(
        select(Workspace).where(
            Workspace.trial_ends_at.is_not(None), Workspace.trial_ends_at <= _now()
        )
    ).all():
        subscription = db.scalar(
            select(Subscription).where(Subscription.workspace_id == workspace.id)
        )
        workspace.trial_ends_at = None
        if subscription is None or subscription.status not in PAID_STATUSES | {"past_due"}:
            workspace.plan = "free"
            audit(db, workspace.id, None, "billing.trial_ended", "workspace", workspace.id)
            expired += 1
    db.commit()
    return expired


# --- checkout and portal -------------------------------------------------------------------------


def _return_url(path: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}{path}"


def create_checkout(db: Session, workspace: Workspace, user: User, plan: str, interval: str) -> str:
    price = prices().get(f"{plan}:{interval}")
    if price is None:
        raise ValidationFailedError(f"The {plan} plan isn't available to buy {interval}ly")
    client = StripeClient()
    row = subscription_row(db, workspace.id)
    if not row.stripe_customer_id:
        customer = client.create_customer(
            email=user.email, name=workspace.name, workspace_id=workspace.id
        )
        row.stripe_customer_id = customer["id"]
        db.commit()
    params: dict[str, Any] = {
        "mode": "subscription",
        "customer": row.stripe_customer_id,
        "client_reference_id": str(workspace.id),
        "line_items": [{"price": price, "quantity": 1}],
        "success_url": _return_url("/settings/usage?checkout=success"),
        "cancel_url": _return_url("/settings/usage?checkout=cancelled"),
        "allow_promotion_codes": True,
        "subscription_data": {"metadata": {"workspace_id": workspace.id}},
        "metadata": {"workspace_id": workspace.id},
    }
    if settings.stripe_automatic_tax:
        params["automatic_tax"] = {"enabled": True}
        params["customer_update"] = {"address": "auto", "name": "auto"}
    session = client.create_checkout_session(params)
    audit(
        db,
        workspace.id,
        user.id,
        "billing.checkout_started",
        "workspace",
        workspace.id,
        {"plan": plan, "interval": interval},
    )
    db.commit()
    return str(session["url"])


def create_portal(db: Session, workspace: Workspace) -> str:
    row = db.scalar(select(Subscription).where(Subscription.workspace_id == workspace.id))
    if row is None or not row.stripe_customer_id:
        raise ValidationFailedError("There's no billing account yet. Choose a plan first.")
    session = StripeClient().create_portal_session(
        customer=row.stripe_customer_id, return_url=_return_url("/settings/usage")
    )
    return str(session["url"])


def list_invoices(db: Session, workspace: Workspace) -> list[dict[str, Any]]:
    row = db.scalar(select(Subscription).where(Subscription.workspace_id == workspace.id))
    if row is None or not row.stripe_customer_id:
        return []
    invoices = StripeClient().list_invoices(row.stripe_customer_id).get("data", [])
    return [
        {
            "id": inv.get("id"),
            "number": inv.get("number"),
            "status": inv.get("status"),
            "amount_due": inv.get("amount_due", 0),
            "amount_paid": inv.get("amount_paid", 0),
            "currency": inv.get("currency", "usd"),
            "created": _ts(inv.get("created")),
            "hosted_invoice_url": inv.get("hosted_invoice_url"),
            "invoice_pdf": inv.get("invoice_pdf"),
        }
        for inv in invoices
    ]


# --- webhooks ------------------------------------------------------------------------------------


def _workspace_for(db: Session, obj: dict[str, Any]) -> int | None:
    metadata = obj.get("metadata") or {}
    for candidate in (metadata.get("workspace_id"), obj.get("client_reference_id")):
        if candidate and str(candidate).isdigit():
            return int(candidate)
    customer = obj.get("customer")
    if customer:
        row = db.scalar(select(Subscription).where(Subscription.stripe_customer_id == customer))
        if row is not None:
            return row.workspace_id
    return None


def reconcile(db: Session, workspace: Workspace, sub: dict[str, Any]) -> Subscription:
    """Bring the workspace's plan in line with a Stripe subscription object."""
    row = subscription_row(db, workspace.id)
    items = (sub.get("items") or {}).get("data") or []
    price = (items[0].get("price") or {}).get("id") if items else None
    plan, interval = plan_for_price(price) if price else (None, None)
    status = sub.get("status")
    previous_plan = workspace.plan

    row.stripe_customer_id = sub.get("customer") or row.stripe_customer_id
    row.stripe_subscription_id = sub.get("id")
    row.status = status
    row.plan = plan or row.plan
    row.interval = interval or row.interval
    row.current_period_end = _ts(sub.get("current_period_end"))
    row.cancel_at_period_end = bool(sub.get("cancel_at_period_end"))
    row.seats = items[0].get("quantity") if items else None

    if status in PAID_STATUSES and plan:
        workspace.plan = plan
        workspace.trial_ends_at = None
        row.past_due_since = None
        _lift_dunning(workspace)
    elif status == "past_due":
        if row.past_due_since is None:
            notify_events.payment_failed(db, workspace)
        row.past_due_since = row.past_due_since or _now()
    elif status in ENDED_STATUSES:
        workspace.plan = "free"
        row.past_due_since = None
        _lift_dunning(workspace)
    if workspace.plan != previous_plan:
        audit(
            db,
            workspace.id,
            None,
            "billing.plan_changed",
            "workspace",
            workspace.id,
            {"from": previous_plan, "to": workspace.plan, "status": status},
        )
    return row


def _lift_dunning(workspace: Workspace) -> None:
    if workspace.sending_suspended_at and (workspace.sending_suspended_reason or "").startswith(
        DUNNING_REASON
    ):
        workspace.sending_suspended_at = None
        workspace.sending_suspended_reason = None


def handle_webhook(db: Session, payload: bytes, signature: str) -> str:
    """Verify, store once and apply a Stripe event. Returns what happened (for logs and tests)."""
    verify_signature(payload, signature, settings.stripe_webhook_secret)
    event = json.loads(payload)
    obj = (event.get("data") or {}).get("object") or {}
    with system_session(db):
        record = BillingEvent(
            stripe_event_id=event["id"], type=event.get("type", ""), payload=event
        )
        db.add(record)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return "duplicate"
        if record.type not in HANDLED_EVENTS:
            record.processed_at = _now()
            db.commit()
            return "ignored"
        workspace_id = _workspace_for(db, obj)
        record.workspace_id = workspace_id
        workspace = db.get(Workspace, workspace_id) if workspace_id else None
        if workspace is None:
            record.error = "No workspace for this event"
            db.commit()
            return "unmatched"

    with workspace_scope(db, workspace.id):
        try:
            subscription_id = (
                obj.get("subscription") if obj.get("object") != "subscription" else obj.get("id")
            )
            if record.type == "checkout.session.completed" and obj.get("customer"):
                subscription_row(db, workspace.id).stripe_customer_id = obj["customer"]
            if subscription_id:
                # Re-read from Stripe instead of trusting the (possibly stale) event body.
                reconcile(db, workspace, StripeClient().retrieve_subscription(subscription_id))
            record.processed_at = _now()
            db.commit()
        except Exception as exc:
            db.rollback()
            with system_session(db):
                failed = db.scalar(
                    select(BillingEvent).where(BillingEvent.stripe_event_id == event["id"])
                )
                if failed is not None:
                    failed.error = str(exc)[:1000]
                    db.commit()
            raise
    return "processed"


# --- dunning -------------------------------------------------------------------------------------


def enforce_dunning(db: Session) -> int:
    """Daily: pause sending for workspaces past due for longer than the grace period."""
    cutoff = _now() - timedelta(days=settings.billing_grace_days)
    paused = 0
    for row in db.scalars(
        select(Subscription).where(
            Subscription.status == "past_due", Subscription.past_due_since <= cutoff
        )
    ).all():
        workspace = db.get(Workspace, row.workspace_id)
        if workspace is None or workspace.sending_suspended_at is not None:
            continue
        workspace.sending_suspended_at = _now()
        workspace.sending_suspended_reason = (
            f"{DUNNING_REASON}: update your payment method to resume sending"
        )
        audit(db, workspace.id, None, "billing.sending_paused", "workspace", workspace.id)
        paused += 1
    db.commit()
    return paused


def grace_ends_at(row: Subscription | None) -> datetime | None:
    since = _aware(row.past_due_since) if row else None
    return since + timedelta(days=settings.billing_grace_days) if since else None
