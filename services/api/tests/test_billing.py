import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.billing import BillingEvent, Subscription
from app.models.user import User
from app.models.workspace import Workspace
from app.services.billing import stripe_billing
from app.services.billing.stripe_client import StripeClient, encode
from tests.conftest import TestingSessionLocal, auth_headers, get_client

WEBHOOK_SECRET = "whsec_test_secret"
PRICES = {"starter:month": "price_starter_m", "pro:month": "price_pro_m", "pro:year": "price_pro_y"}


class FakeStripe:
    def __init__(self):
        self.calls = []
        self.subscription = {
            "id": "sub_1",
            "object": "subscription",
            "customer": "cus_1",
            "status": "active",
            "current_period_end": int(time.time()) + 30 * 86400,
            "cancel_at_period_end": False,
            "items": {"data": [{"price": {"id": "price_pro_m"}, "quantity": 1}]},
            "metadata": {},
        }

    def __call__(self, method, path, params=None):
        self.calls.append((method, path, params or {}))
        if path == "customers":
            return {"id": "cus_1"}
        if path == "checkout/sessions":
            return {"id": "cs_1", "url": "https://checkout.stripe.com/c/pay/cs_1"}
        if path == "billing_portal/sessions":
            return {"url": "https://billing.stripe.com/p/session/1"}
        if path.startswith("subscriptions/"):
            return self.subscription
        if path == "invoices":
            return {
                "data": [
                    {
                        "id": "in_1",
                        "number": "LG-0001",
                        "status": "paid",
                        "amount_due": 9900,
                        "amount_paid": 9900,
                        "currency": "gbp",
                        "created": int(time.time()),
                        "hosted_invoice_url": "https://invoice.stripe.com/i/1",
                        "invoice_pdf": "https://pay.stripe.com/invoice/1/pdf",
                    }
                ]
            }
        raise AssertionError(f"unexpected Stripe call {method} {path}")


@pytest.fixture
def stripe(monkeypatch):
    fake = FakeStripe()
    monkeypatch.setattr(settings, "feature_billing", True)
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_123")
    monkeypatch.setattr(settings, "stripe_webhook_secret", WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "stripe_prices", json.dumps(PRICES))
    monkeypatch.setattr(StripeClient, "request", fake)
    return fake


def _signed(client, event, *, secret=WEBHOOK_SECRET, timestamp=None):
    body = json.dumps(event).encode()
    t = timestamp or int(time.time())
    sig = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return client.post(
        "/billing/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": f"t={t},v1={sig}", "Content-Type": "application/json"},
    )


def _event(event_id, event_type, obj):
    return {"id": event_id, "type": event_type, "data": {"object": obj}}


def _workspace(email="test@example.com"):
    db = TestingSessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        return db.get(Workspace, user.last_workspace_id)
    finally:
        db.close()


def _checkout_completed(client, workspace_id, event_id="evt_1"):
    return _signed(
        client,
        _event(
            event_id,
            "checkout.session.completed",
            {
                "object": "checkout.session",
                "customer": "cus_1",
                "subscription": "sub_1",
                "client_reference_id": str(workspace_id),
            },
        ),
    )


def test_stripe_form_encoding():
    assert encode(
        {"line_items": [{"price": "p", "quantity": 1}], "metadata": {"w": 3}, "x": True, "n": None}
    ) == [
        ("line_items[0][price]", "p"),
        ("line_items[0][quantity]", "1"),
        ("metadata[w]", "3"),
        ("x", "true"),
    ]


def test_billing_off_by_default():
    client = get_client()
    headers = auth_headers(client)
    summary = client.get("/billing", headers=headers).json()
    assert summary["billing_enabled"] is False
    assert summary["purchasable"] == []
    assert (
        client.post("/billing/checkout", headers=headers, json={"plan": "pro"}).status_code == 501
    )
    assert client.post("/billing/webhooks/stripe", content=b"{}").status_code == 404


def test_checkout_and_portal(stripe):
    client = get_client()
    headers = auth_headers(client)
    summary = client.get("/billing", headers=headers).json()
    assert summary["billing_enabled"] is True
    assert summary["purchasable"] == ["pro:month", "pro:year", "starter:month"]

    assert (
        client.post("/billing/portal", headers=headers).status_code == 400
    )  # no billing account yet
    assert (
        client.post(
            "/billing/checkout", headers=headers, json={"plan": "starter", "interval": "year"}
        ).status_code
        == 400
    )

    response = client.post(
        "/billing/checkout", headers=headers, json={"plan": "pro", "interval": "month"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["url"].startswith("https://checkout.stripe.com/")
    session = next(params for method, path, params in stripe.calls if path == "checkout/sessions")
    assert session["line_items"] == [{"price": "price_pro_m", "quantity": 1}]
    assert session["client_reference_id"] == str(_workspace().id)
    assert session["mode"] == "subscription"

    # The Stripe customer is created once and reused.
    client.post("/billing/checkout", headers=headers, json={"plan": "pro", "interval": "year"})
    assert [path for _, path, _ in stripe.calls].count("customers") == 1

    portal = client.post("/billing/portal", headers=headers)
    assert portal.json()["url"].startswith("https://billing.stripe.com/")
    invoices = client.get("/billing/invoices", headers=headers).json()
    assert invoices[0]["number"] == "LG-0001" and invoices[0]["amount_paid"] == 9900


def test_only_billing_managers_can_buy(stripe):
    from app.services.platform_email.mailer import OUTBOX

    client = get_client()
    owner = auth_headers(client)
    db = TestingSessionLocal()
    try:
        db.get(Workspace, _workspace().id).plan = "pro"
        db.commit()
    finally:
        db.close()
    client.post(
        "/workspaces/current/invitations",
        headers=owner,
        json={"email": "admin@example.com", "role": "admin"},
    )
    token = next(
        m.text.split("/invite/")[1].split()[0]
        for m in reversed(OUTBOX)
        if m.to == "admin@example.com"
    )
    admin = auth_headers(client, "admin@example.com")
    workspace_id = client.post(f"/invitations/{token}/accept", headers=admin).json()["id"]
    admin = {**admin, "X-Workspace-Id": str(workspace_id)}
    assert client.post("/billing/checkout", headers=admin, json={"plan": "pro"}).status_code == 403
    assert client.post("/billing/portal", headers=admin).status_code == 403


def test_webhooks_reconcile_the_plan(stripe):
    client = get_client()
    headers = auth_headers(client)
    workspace_id = _workspace().id

    result = _checkout_completed(client, workspace_id)
    assert result.status_code == 200, result.text
    assert result.json() == {"result": "processed"}
    assert _workspace().plan == "pro"
    summary = client.get("/billing", headers=headers).json()
    assert summary["subscription"]["status"] == "active"
    assert summary["subscription"]["interval"] == "month"
    assert summary["subscription"]["has_billing_account"] is True

    # Stripe retries are harmless.
    assert _checkout_completed(client, workspace_id).json() == {"result": "duplicate"}

    # Bad or stale signatures are refused.
    event = _event(
        "evt_x", "invoice.paid", {"object": "invoice", "customer": "cus_1", "subscription": "sub_1"}
    )
    assert _signed(client, event, secret="whsec_wrong").status_code == 400
    assert _signed(client, event, timestamp=int(time.time()) - 3600).status_code == 400

    # An out-of-order "updated" event after cancellation: we re-read Stripe, which says canceled.
    stripe.subscription = {**stripe.subscription, "status": "canceled"}
    _signed(client, _event("evt_2", "customer.subscription.deleted", stripe.subscription))
    _signed(
        client,
        _event(
            "evt_3", "customer.subscription.updated", {**stripe.subscription, "status": "active"}
        ),
    )
    assert _workspace().plan == "free"

    assert _signed(client, _event("evt_4", "charge.refunded", {"object": "charge"})).json() == {
        "result": "ignored"
    }
    unmatched = _signed(
        client,
        _event(
            "evt_5",
            "invoice.paid",
            {"object": "invoice", "customer": "cus_unknown", "subscription": "sub_9"},
        ),
    )
    assert unmatched.json() == {"result": "unmatched"}
    db = TestingSessionLocal()
    try:
        assert db.scalar(select(BillingEvent).where(BillingEvent.stripe_event_id == "evt_5")).error
    finally:
        db.close()


def test_dunning_pauses_then_resumes_sending(stripe):
    client = get_client()
    headers = auth_headers(client)
    workspace_id = _workspace().id
    _checkout_completed(client, workspace_id)

    stripe.subscription = {**stripe.subscription, "status": "past_due"}
    _signed(
        client,
        _event(
            "evt_pd",
            "invoice.payment_failed",
            {"object": "invoice", "customer": "cus_1", "subscription": "sub_1"},
        ),
    )
    summary = client.get("/billing", headers=headers).json()
    assert summary["subscription"]["status"] == "past_due"
    assert summary["subscription"]["grace_ends_at"] is not None
    assert summary["plan"] == "pro"  # still usable during the grace period

    db = TestingSessionLocal()
    try:
        assert stripe_billing.enforce_dunning(db) == 0  # within grace
        row = db.scalar(select(Subscription).where(Subscription.workspace_id == workspace_id))
        row.past_due_since = datetime.now(UTC) - timedelta(days=settings.billing_grace_days + 1)
        db.commit()
        assert stripe_billing.enforce_dunning(db) == 1
    finally:
        db.close()
    assert client.get("/billing", headers=headers).json()["sending_paused_for_payment"] is True
    assert _workspace().sending_suspended_at is not None

    stripe.subscription = {**stripe.subscription, "status": "active"}
    _signed(
        client,
        _event(
            "evt_paid",
            "invoice.paid",
            {"object": "invoice", "customer": "cus_1", "subscription": "sub_1"},
        ),
    )
    workspace = _workspace()
    assert workspace.sending_suspended_at is None
    assert client.get("/billing", headers=headers).json()["subscription"]["past_due_since"] is None


def test_admin_suspensions_are_not_lifted_by_payments(stripe):
    client = get_client()
    auth_headers(client)
    workspace_id = _workspace().id
    db = TestingSessionLocal()
    try:
        workspace = db.get(Workspace, workspace_id)
        workspace.sending_suspended_at = datetime.now(UTC)
        workspace.sending_suspended_reason = "Complaint spike"
        db.commit()
    finally:
        db.close()
    _checkout_completed(client, workspace_id)
    assert _workspace().sending_suspended_reason == "Complaint spike"


def test_trials_start_and_expire(stripe):
    client = get_client()
    auth_headers(client)
    workspace = _workspace()
    assert workspace.plan == "starter"
    assert workspace.trial_ends_at is not None

    auth_headers(client, "paying@example.com")
    paying = _workspace("paying@example.com")
    _checkout_completed(client, paying.id, event_id="evt_pay")  # subscribes to pro

    db = TestingSessionLocal()
    try:
        for ws in db.scalars(select(Workspace)).all():
            ws.trial_ends_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
        assert stripe_billing.expire_trials(db) == 1
    finally:
        db.close()
    assert _workspace().plan == "free"
    assert _workspace("paying@example.com").plan == "pro"
