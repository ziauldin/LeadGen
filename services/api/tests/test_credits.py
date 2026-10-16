import json

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.billing import CreditTransaction
from app.models.workspace import Workspace
from app.services.billing import credits
from app.services.billing.stripe_client import StripeClient
from app.services.billing.usage import check_quota, record_usage, remaining
from tests.conftest import TestingSessionLocal, auth_headers, get_client, login
from tests.sending_helpers import approved_message
from tests.test_billing import WEBHOOK_SECRET, FakeStripe, _event, _signed, _workspace

LEADS = ("alex@example-foods.co.uk", "jo@example-foods.co.uk", "sam@example-foods.co.uk")


def _db():
    db = TestingSessionLocal()
    db.info["tenant_bypass"] = True
    return db


def _set(workspace_id: int, **values) -> None:
    db = _db()
    try:
        workspace = db.get(Workspace, workspace_id)
        for key, value in values.items():
            setattr(workspace, key, value)
        db.commit()
    finally:
        db.close()


def test_credit_maths():
    assert credits.credits_for("monthly_verifications", 3) == 3
    assert credits.credits_for("monthly_llm_tokens", 1) == 1
    assert credits.credits_for("monthly_llm_tokens", 1500) == 2
    assert credits.credits_for("monthly_llm_tokens", 0) == 0


def test_usage_beyond_the_plan_draws_on_credits():
    client = get_client()
    auth_headers(client)
    workspace_id = _workspace().id
    _set(workspace_id, plan_overrides={"monthly_verifications": 2})
    db = _db()
    try:
        workspace = db.get(Workspace, workspace_id)
        check_quota(db, workspace, "monthly_verifications", 2)
        with pytest.raises(Exception, match="Plan limit"):
            check_quota(db, workspace, "monthly_verifications", 3)
        credits.grant(db, workspace_id, 5, kind="grant", note="test")
        db.commit()
        assert remaining(db, workspace, "monthly_verifications") == 7
        check_quota(db, workspace, "monthly_verifications", 7)
        record_usage(db, workspace_id, "monthly_verifications", 3)  # 2 included + 1 credit
        record_usage(db, workspace_id, "monthly_verifications", 2)  # 2 credits
        db.commit()
        assert credits.balance(db, workspace_id) == 2
        usage = db.scalars(select(CreditTransaction).where(CreditTransaction.kind == "usage")).all()
        assert len(usage) == 1 and usage[0].amount == -3 and usage[0].balance_after == 2
        with pytest.raises(Exception, match="Plan limit"):
            check_quota(db, workspace, "monthly_verifications", 3)
        # Metrics that credits don't cover are unaffected.
        assert remaining(db, workspace, "monthly_sends") == 500
    finally:
        db.close()


def test_platform_verification_spends_credits_after_the_allowance(monkeypatch):
    monkeypatch.setattr(settings, "platform_verification_provider", "mock")
    client = get_client()
    headers, _campaign, _ids = approved_message(client, emails=LEADS)
    workspace_id = _workspace().id
    _set(workspace_id, plan_overrides={"monthly_verifications": 1})
    db = _db()
    try:
        credits.grant(db, workspace_id, 1, kind="grant", note="test")
        db.commit()
    finally:
        db.close()
    lead_ids = [lead["id"] for lead in client.get("/leads", headers=headers).json()["items"]]
    client.post("/leads/bulk", headers=headers, json={"action": "verify", "lead_ids": lead_ids})
    summary = client.get("/billing", headers=headers).json()
    usage = {u["metric"]: u for u in summary["usage"]}
    assert usage["monthly_verifications"]["used"] == 2  # 1 included + 1 paid with a credit
    assert summary["credits"]["balance"] == 0
    assert summary["credits"]["units"]["monthly_llm_tokens"] == 1000
    history = client.get("/billing/credits", headers=headers).json()
    assert [(row["kind"], row["amount"]) for row in history] == [("usage", -1), ("grant", 1)]


def test_buying_a_credit_pack(monkeypatch):
    session = {
        "id": "cs_credits_1",
        "object": "checkout.session",
        "payment_status": "paid",
        "customer": "cus_1",
        "metadata": {},
    }

    class CreditStripe(FakeStripe):
        def __call__(self, method, path, params=None):
            if path == "checkout/sessions/cs_credits_1":
                self.calls.append((method, path, params or {}))
                return session
            return super().__call__(method, path, params)

    fake = CreditStripe()
    monkeypatch.setattr(settings, "feature_billing", True)
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_123")
    monkeypatch.setattr(settings, "stripe_webhook_secret", WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "stripe_credit_prices", json.dumps({"1000": "price_credits_1k"}))
    monkeypatch.setattr(StripeClient, "request", fake)

    client = get_client()
    headers = auth_headers(client)
    workspace_id = _workspace().id
    packs = {
        p["credits"]: p for p in client.get("/billing", headers=headers).json()["credits"]["packs"]
    }
    assert packs[1000]["purchasable"] is True and packs[5000]["purchasable"] is False
    assert (
        client.post(
            "/billing/credits/checkout", headers=headers, json={"credits": 5000}
        ).status_code
        == 400
    )

    started = client.post("/billing/credits/checkout", headers=headers, json={"credits": 1000})
    assert started.status_code == 200, started.text
    created = next(params for method, path, params in fake.calls if path == "checkout/sessions")
    assert created["mode"] == "payment"
    assert created["line_items"] == [{"price": "price_credits_1k", "quantity": 1}]
    assert created["metadata"] == {"workspace_id": workspace_id, "kind": "credits", "credits": 1000}

    session["metadata"] = {"workspace_id": str(workspace_id), "kind": "credits", "credits": "1000"}
    body = {**session, "client_reference_id": str(workspace_id)}
    assert _signed(client, _event("evt_c1", "checkout.session.completed", body)).json() == {
        "result": "processed"
    }
    assert client.get("/billing", headers=headers).json()["credits"]["balance"] == 1000
    # Stripe retries and the async-payment event don't add the credits twice.
    assert _signed(client, _event("evt_c1", "checkout.session.completed", body)).json() == {
        "result": "duplicate"
    }
    _signed(client, _event("evt_c2", "checkout.session.async_payment_succeeded", body))
    assert client.get("/billing", headers=headers).json()["credits"]["balance"] == 1000

    # An unpaid session (e.g. a bank transfer still pending) adds nothing yet.
    session.update(id="cs_credits_1", payment_status="unpaid")
    _signed(client, _event("evt_c3", "checkout.session.completed", {**body, "id": "cs_credits_1"}))
    assert client.get("/billing", headers=headers).json()["credits"]["balance"] == 1000


def test_admin_credit_grants_and_public_packs(monkeypatch):
    monkeypatch.setattr(settings, "superuser_require_mfa", False)
    client = get_client()
    headers = auth_headers(client)
    workspace_id = _workspace().id
    assert client.post(
        f"/admin/workspaces/{workspace_id}/credits",
        headers=headers,
        json={"amount": 50, "note": "Goodwill"},
    ).status_code in (403, 404)

    db = _db()
    try:
        from app.models.user import User

        user = db.scalar(select(User).where(User.email == "test@example.com"))
        user.is_superuser = True
        db.commit()
    finally:
        db.close()
    admin_headers = login(client, "test@example.com")  # a fresh token with superuser rights
    granted = client.post(
        f"/admin/workspaces/{workspace_id}/credits",
        headers=admin_headers,
        json={"amount": 50, "note": "Goodwill"},
    )
    assert granted.status_code == 200, granted.text
    assert granted.json() == {"balance": 50}
    taken = client.post(
        f"/admin/workspaces/{workspace_id}/credits",
        headers=admin_headers,
        json={"amount": -20, "note": "Correction"},
    )
    assert taken.json() == {"balance": 30}
    assert (
        client.post(
            f"/admin/workspaces/{workspace_id}/credits",
            headers=admin_headers,
            json={"amount": 0, "note": "Nothing"},
        ).status_code
        == 400
    )

    public = client.get("/billing/credit-packs").json()
    assert [p["credits"] for p in public["packs"]] == [1000, 5000, 20000]
    assert public["packs"][0]["amount"] == 10 and public["packs"][0]["currency"] == "USD"
    assert public["units"]["monthly_verifications"] == 1
