import json

from app.core.config import settings
from app.services.platform_email.mailer import OUTBOX
from tests.conftest import get_client

MESSAGE = {
    "name": "Ada",
    "email": "ada@example.co.uk",
    "company": "Analytical Ltd",
    "topic": "sales",
    "message": "We'd like a demo for a team of twelve.",
}


def test_public_plans(monkeypatch):
    monkeypatch.setattr(
        settings,
        "plan_display_prices",
        json.dumps({"currency": "GBP", "free": {"month": 0}, "pro": {"month": 149, "year": 1490}}),
    )
    client = get_client()
    plans = {p["name"]: p for p in client.get("/billing/plans").json()}
    assert list(plans) == ["free", "starter", "pro", "enterprise"]
    assert plans["pro"]["prices"] == {"month": 149, "year": 1490}
    assert plans["pro"]["currency"] == "GBP"
    assert plans["starter"]["prices"] is None
    assert plans["pro"]["limits"]["monthly_sends"] == 50000
    assert plans["enterprise"]["features"]["saml"] is True
    assert plans["pro"]["purchasable"] == []  # billing is off


def test_default_display_prices():
    client = get_client()
    plans = {p["name"]: p for p in client.get("/billing/plans").json()}
    assert plans["starter"]["prices"] == {"month": 39, "year": 390}
    assert plans["pro"]["prices"] == {"month": 99, "year": 990}
    assert plans["enterprise"]["prices"] is None  # "Custom" on the pricing page
    assert plans["pro"]["limits"]["max_mailboxes"] == 25


def test_contact_form(monkeypatch):
    monkeypatch.setattr(settings, "support_email", "sales@leadsgen-test.co.uk")
    client = get_client()
    response = client.post("/contact", json=MESSAGE)
    assert response.status_code == 200, response.text
    sent = [m for m in OUTBOX if m.tags.get("kind") == "contact"]
    assert len(sent) == 1
    assert sent[0].to == "sales@leadsgen-test.co.uk"
    assert "ada@example.co.uk" in sent[0].text

    # Bots that fill the hidden field are quietly dropped.
    assert client.post("/contact", json={**MESSAGE, "website": "spam.example"}).status_code == 200
    assert len([m for m in OUTBOX if m.tags.get("kind") == "contact"]) == 1

    assert client.post("/contact", json={**MESSAGE, "message": "short"}).status_code == 422
    assert client.post("/contact", json={**MESSAGE, "topic": "hack"}).status_code == 422


def test_contact_is_rate_limited():
    client = get_client()
    statuses = [client.post("/contact", json=MESSAGE).status_code for _ in range(6)]
    assert statuses[:5] == [200] * 5
    assert statuses[5] == 429


def test_feedback_needs_sign_in_and_reaches_support(monkeypatch):
    from tests.conftest import auth_headers

    monkeypatch.setattr(settings, "support_email", "product@leadsgen-test.co.uk")
    client = get_client()
    assert (
        client.post("/feedback", json={"kind": "idea", "message": "Dark mode please"}).status_code
        == 401
    )
    headers = auth_headers(client)
    response = client.post(
        "/feedback",
        headers=headers,
        json={"kind": "bug", "message": "Export button does nothing", "page": "/leads"},
    )
    assert response.status_code == 200
    sent = [m for m in OUTBOX if m.tags.get("kind") == "feedback"][-1]
    assert sent.to == "product@leadsgen-test.co.uk"
    assert "[feedback:bug]" in sent.subject
    assert "Page: /leads" in sent.text
    assert (
        client.post(
            "/feedback", headers=headers, json={"kind": "rant", "message": "x" * 10}
        ).status_code
        == 422
    )
