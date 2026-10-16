import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.http import FetchError, FetchResult
from app.models.developer import ApiKey, WebhookDelivery, WebhookEndpoint
from app.models.lead import Lead
from app.models.user import User
from app.models.workspace import Workspace
from app.services.developer import webhooks
from app.services.developer.webhooks import RETRY_SCHEDULE
from app.workers.outbound_webhook_jobs import retry_due_webhooks
from tests.conftest import TestingSessionLocal, auth_headers, get_client

OWNER = "owner@example.com"
NICHE = {"name": "Dentists", "country": "UK", "industry": "Dental"}
ALL_SCOPES = [
    "leads:read",
    "leads:write",
    "campaigns:read",
    "campaigns:write",
    "replies:read",
    "suppressions:read",
    "suppressions:write",
]


@pytest.fixture(autouse=True)
def public_api(monkeypatch):
    monkeypatch.setattr(settings, "feature_public_api", True)


class FakeReceiver:
    def __init__(self):
        self.calls = []
        self.status = 200
        self.error = None

    def __call__(self, client, url, content, *, timeout, max_bytes, headers=None):
        self.calls.append({"url": url, "body": content, "headers": headers})
        if self.error:
            raise FetchError(self.error)
        return FetchResult(url=url, status_code=self.status, text="ok", content_type="text/plain")


@pytest.fixture
def receiver(monkeypatch):
    fake = FakeReceiver()
    monkeypatch.setattr(webhooks, "safe_post_bytes", fake)
    return fake


def _set_plan(email, plan):
    db = TestingSessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        workspace = db.get(Workspace, user.last_workspace_id)
        workspace.plan = plan
        db.commit()
        return workspace.id
    finally:
        db.close()


def _owner(client, email=OWNER, plan="pro"):
    headers = auth_headers(client, email)
    _set_plan(email, plan)
    return headers


def _key(client, headers, scopes=None, name="Zapier"):
    response = client.post(
        "/api-keys", headers=headers, json={"name": name, "scopes": scopes or ALL_SCOPES}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _bearer(raw):
    return {"Authorization": f"Bearer {raw}"}


def test_feature_flag_and_plan_gate(monkeypatch):
    client = get_client()
    headers = _owner(client, plan="free")
    denied = client.post("/api-keys", headers=headers, json={"name": "x", "scopes": ["leads:read"]})
    assert denied.status_code == 403
    assert denied.json()["code"] == "plan_feature_required"

    _set_plan(OWNER, "pro")
    raw = _key(client, headers)["key"]
    assert client.get("/v1/me", headers=_bearer(raw)).status_code == 200
    # Downgrading turns the key off.
    _set_plan(OWNER, "free")
    assert client.get("/v1/me", headers=_bearer(raw)).status_code == 403

    monkeypatch.setattr(settings, "feature_public_api", False)
    assert client.get("/v1/me", headers=_bearer(raw)).status_code == 404


def test_key_lifecycle_and_storage():
    client = get_client()
    headers = _owner(client)
    created = _key(client, headers, ["leads:read"])
    raw = created["key"]
    assert raw.startswith("lg_live_")
    assert created["prefix"] == raw[:16]

    listing = client.get("/api-keys", headers=headers).json()
    assert "key" not in listing[0]
    db = TestingSessionLocal()
    try:
        stored = db.scalar(select(ApiKey))
        assert stored.key_hash == hashlib.sha256(raw.encode()).hexdigest()
        assert raw not in json.dumps(
            {c.key: str(getattr(stored, c.key)) for c in stored.__table__.columns}
        )
    finally:
        db.close()

    me = client.get("/v1/me", headers=_bearer(raw))
    assert me.status_code == 200
    assert me.json()["scopes"] == ["leads:read"]
    assert client.get("/api-keys", headers=headers).json()[0]["last_used_at"] is not None

    assert client.get("/v1/me", headers=_bearer(raw + "x")).status_code == 401
    assert client.get("/v1/me", headers=_bearer("lg_live_short")).status_code == 401
    assert client.get("/v1/me").status_code == 401

    assert client.delete(f"/api-keys/{created['id']}", headers=headers).status_code == 204
    assert client.get("/v1/me", headers=_bearer(raw)).status_code == 401


def test_expired_keys_and_unknown_scopes():
    client = get_client()
    headers = _owner(client)
    bad = client.post("/api-keys", headers=headers, json={"name": "x", "scopes": ["everything"]})
    assert bad.status_code == 400
    created = client.post(
        "/api-keys",
        headers=headers,
        json={"name": "x", "scopes": ["leads:read"], "expires_in_days": 1},
    ).json()
    db = TestingSessionLocal()
    try:
        key = db.get(ApiKey, created["id"])
        key.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()
    assert client.get("/v1/me", headers=_bearer(created["key"])).status_code == 401


def test_scopes_leads_and_idempotency():
    client = get_client()
    headers = _owner(client)
    niche_id = client.post("/niches", headers=headers, json=NICHE).json()["id"]
    reader = _bearer(_key(client, headers, ["leads:read"], name="reader")["key"])
    writer = _bearer(_key(client, headers, ["leads:read", "leads:write"], name="writer")["key"])

    lead = {
        "niche_id": niche_id,
        "full_name": "Dr Jo Smith",
        "source_url": "https://example.com/dentists",
        "compliance_source_note": "Public practice listing",
        "emails": ["Jo.Smith@smile-dental.co.uk"],
    }
    assert client.post("/v1/leads", headers=reader, json=lead).status_code == 403

    first = client.post("/v1/leads", headers={**writer, "Idempotency-Key": "abc-1"}, json=lead)
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["source_provider"] == "api"
    assert body["primary_email"] == "jo.smith@smile-dental.co.uk"
    again = client.post("/v1/leads", headers={**writer, "Idempotency-Key": "abc-1"}, json=lead)
    assert again.status_code == 201
    assert again.headers["Idempotent-Replayed"] == "true"
    assert again.json()["id"] == body["id"]
    clash = client.post(
        "/v1/leads",
        headers={**writer, "Idempotency-Key": "abc-1"},
        json={**lead, "full_name": "Other"},
    )
    assert clash.status_code == 422

    listing = client.get("/v1/leads", headers=reader, params={"status": "new"}).json()
    assert listing["total"] == 1
    assert (
        client.get(f"/v1/leads/{body['id']}", headers=reader).json()["full_name"] == "Dr Jo Smith"
    )
    updated = client.patch(
        f"/v1/leads/{body['id']}", headers=writer, json={"job_title": "Principal"}
    )
    assert updated.json()["job_title"] == "Principal"
    assert client.get("/v1/companies", headers=reader).status_code == 200


def test_keys_are_scoped_to_their_workspace_and_creator():
    client = get_client()
    owner = _owner(client)
    niche_id = client.post("/niches", headers=owner, json=NICHE).json()["id"]
    lead_id = client.post(
        "/leads", headers=owner, json={"niche_id": niche_id, "full_name": "Jo"}
    ).json()["id"]

    other = _owner(client, "other@example.com")
    other_key = _bearer(_key(client, other)["key"])
    assert client.get(f"/v1/leads/{lead_id}", headers=other_key).status_code == 404
    assert client.get("/v1/leads", headers=other_key).json()["total"] == 0

    # An admin's key stops working once they leave the workspace.
    from app.services.platform_email.mailer import OUTBOX

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
    admin_key = _bearer(_key(client, admin, ["leads:read"])["key"])
    assert client.get(f"/v1/leads/{lead_id}", headers=admin_key).status_code == 200
    db = TestingSessionLocal()
    try:
        admin_id = db.scalar(select(User.id).where(User.email == "admin@example.com"))
    finally:
        db.close()
    assert (
        client.delete(f"/workspaces/current/members/{admin_id}", headers=owner).status_code == 204
    )
    assert client.get(f"/v1/leads/{lead_id}", headers=admin_key).status_code == 401


def test_suppressions_campaigns_and_rate_limit(monkeypatch):
    client = get_client()
    headers = _owner(client)
    key = _bearer(_key(client, headers)["key"])
    created = client.post(
        "/v1/suppressions",
        headers={**key, "Idempotency-Key": "s1"},
        json={"email": "no@acme.co.uk"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["source"] == "api"
    replay = client.post(
        "/v1/suppressions",
        headers={**key, "Idempotency-Key": "s1"},
        json={"email": "no@acme.co.uk"},
    )
    assert replay.json()["id"] == created.json()["id"]
    assert client.get("/v1/suppressions", headers=key).json()["total"] == 1
    assert client.delete(f"/v1/suppressions/{created.json()['id']}", headers=key).status_code == 204
    assert client.get("/v1/campaigns", headers=key).json()["total"] == 0
    assert client.get("/v1/replies", headers=key).json()["total"] == 0

    monkeypatch.setattr(settings, "rate_limit_api", "2/minute")
    from app.core.rate_limit import reset_rate_limits

    reset_rate_limits()
    assert client.get("/v1/me", headers=key).status_code == 200
    assert client.get("/v1/me", headers=key).status_code == 200
    assert client.get("/v1/me", headers=key).status_code == 429


def test_public_openapi_lists_only_v1():
    client = get_client()
    schema = client.get("/v1/openapi.json").json()
    assert schema["paths"]
    assert all(path.startswith("/v1/") for path in schema["paths"])
    assert "/v1/leads" in schema["paths"]
    assert schema["components"]["securitySchemes"]["bearer"]["scheme"] == "bearer"


# --- outbound webhooks ---------------------------------------------------------------------------


def _endpoint(client, headers, events=("lead.created",), url="https://hooks.example.com/leadsgen"):
    response = client.post(
        "/webhook-endpoints", headers=headers, json={"url": url, "events": list(events)}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_webhook_url_and_event_validation():
    client = get_client()
    headers = _owner(client)
    for url in (
        "http://localhost/x",
        "https://10.0.0.5/x",
        "ftp://example.com",
        "https://db.internal/x",
    ):
        assert (
            client.post(
                "/webhook-endpoints", headers=headers, json={"url": url, "events": ["lead.created"]}
            ).status_code
            == 400
        )
    assert (
        client.post(
            "/webhook-endpoints",
            headers=headers,
            json={"url": "https://hooks.example.com", "events": ["nope"]},
        ).status_code
        == 400
    )


def test_events_are_signed_and_delivered(receiver):
    client = get_client()
    headers = _owner(client)
    endpoint = _endpoint(client, headers)
    _endpoint(client, headers, events=["reply.received"], url="https://other.example.com/hook")
    secret = endpoint["secret"]
    assert secret.startswith("whsec_")
    assert "secret" not in client.get("/webhook-endpoints", headers=headers).json()[0]

    niche_id = client.post("/niches", headers=headers, json=NICHE).json()["id"]
    lead_id = client.post(
        "/leads", headers=headers, json={"niche_id": niche_id, "full_name": "Jo"}
    ).json()["id"]

    assert len(receiver.calls) == 1  # only the endpoint subscribed to lead.created
    call = receiver.calls[0]
    assert call["url"] == "https://hooks.example.com/leadsgen"
    payload = json.loads(call["body"])
    assert payload["type"] == "lead.created"
    assert payload["data"]["lead"]["id"] == lead_id
    assert call["headers"]["LeadsGen-Event"] == "lead.created"
    timestamp, signature = (
        part.split("=", 1)[1] for part in call["headers"]["LeadsGen-Signature"].split(",")
    )
    expected = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + call["body"], hashlib.sha256
    ).hexdigest()
    assert hmac.compare_digest(signature, expected)

    deliveries = client.get(
        f"/webhook-endpoints/{endpoint['id']}/deliveries", headers=headers
    ).json()
    assert deliveries["items"][0]["status"] == "succeeded"
    assert deliveries["items"][0]["response_status"] == 200

    # Replays keep the event id so receivers can de-duplicate.
    replayed = client.post(
        f"/webhook-deliveries/{deliveries['items'][0]['id']}/replay", headers=headers
    )
    assert replayed.status_code == 200
    assert replayed.json()["event_id"] == payload["id"]
    assert len(receiver.calls) == 2

    ping = client.post(f"/webhook-endpoints/{endpoint['id']}/test", headers=headers).json()
    assert ping["event_type"] == "ping" and ping["status"] == "succeeded"

    rotated = client.post(
        f"/webhook-endpoints/{endpoint['id']}/rotate-secret", headers=headers
    ).json()["secret"]
    assert rotated != secret


def test_failed_deliveries_retry_then_give_up(receiver):
    client = get_client()
    headers = _owner(client)
    endpoint = _endpoint(client, headers)
    receiver.status = 500
    niche_id = client.post("/niches", headers=headers, json=NICHE).json()["id"]
    client.post("/leads", headers=headers, json={"niche_id": niche_id, "full_name": "Jo"})

    db = TestingSessionLocal()
    try:
        delivery = db.scalar(select(WebhookDelivery))
        assert delivery.status == "pending"
        assert delivery.attempts == 1
        assert delivery.error == "Endpoint answered 500"
        delivery_id = delivery.id
    finally:
        db.close()

    # Not due yet: the sweep leaves it alone.
    assert retry_due_webhooks() == 0
    receiver.error = "Request failed: ConnectError"
    for _ in RETRY_SCHEDULE:
        db = TestingSessionLocal()
        try:
            row = db.get(WebhookDelivery, delivery_id)
            row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
        finally:
            db.close()
        assert retry_due_webhooks() == 1

    db = TestingSessionLocal()
    try:
        row = db.get(WebhookDelivery, delivery_id)
        assert row.status == "failed"
        assert row.attempts == len(RETRY_SCHEDULE) + 1
        assert row.next_attempt_at is None
        assert (
            db.get(WebhookEndpoint, endpoint["id"]).consecutive_failures == len(RETRY_SCHEDULE) + 1
        )
    finally:
        db.close()

    # A success resets the failure count.
    receiver.error = None
    receiver.status = 204
    assert (
        client.post(f"/webhook-endpoints/{endpoint['id']}/test", headers=headers).json()["status"]
        == "succeeded"
    )
    db = TestingSessionLocal()
    try:
        assert db.get(WebhookEndpoint, endpoint["id"]).consecutive_failures == 0
    finally:
        db.close()


def test_endpoints_are_disabled_after_repeated_failures(receiver):
    client = get_client()
    headers = _owner(client)
    endpoint = _endpoint(client, headers)
    db = TestingSessionLocal()
    try:
        db.get(WebhookEndpoint, endpoint["id"]).consecutive_failures = (
            webhooks.DISABLE_AFTER_FAILURES - 1
        )
        db.commit()
    finally:
        db.close()
    receiver.status = 410
    client.post(f"/webhook-endpoints/{endpoint['id']}/test", headers=headers)
    listed = client.get("/webhook-endpoints", headers=headers).json()[0]
    assert listed["is_active"] is False
    assert "Disabled after" in listed["disabled_reason"]

    # Nothing is queued for a disabled endpoint; turning it back on resets it.
    niche_id = client.post("/niches", headers=headers, json=NICHE).json()["id"]
    client.post("/leads", headers=headers, json={"niche_id": niche_id, "full_name": "Jo"})
    assert len(receiver.calls) == 1
    enabled = client.patch(
        f"/webhook-endpoints/{endpoint['id']}", headers=headers, json={"is_active": True}
    ).json()
    assert enabled["is_active"] and enabled["consecutive_failures"] == 0


def test_rolled_back_events_are_not_sent(receiver):
    client = get_client()
    headers = _owner(client)
    _endpoint(client, headers)
    niche_id = client.post("/niches", headers=headers, json=NICHE).json()["id"]
    db = TestingSessionLocal()
    try:
        workspace_id = db.scalar(select(User).where(User.email == OWNER)).last_workspace_id
        lead = Lead(workspace_id=workspace_id, niche_id=niche_id, full_name="Ghost")
        db.add(lead)
        db.flush()
        from app.services.developer.events import lead_created

        lead_created(db, lead)
        db.rollback()
        db.commit()
    finally:
        db.close()
    assert receiver.calls == []


def test_send_and_reply_events(receiver):
    from tests.sending_helpers import approved_message

    client = get_client()
    headers, campaign_id, _ids = approved_message(client)
    _set_plan("test@example.com", "pro")
    _endpoint(client, headers, events=["email.sent", "reply.received"])
    assert (
        client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers).json()["sent"] == 1
    )
    client.post("/replies/sync", headers=headers)

    types = [json.loads(call["body"])["type"] for call in receiver.calls]
    assert types[0] == "email.sent"
    assert "reply.received" in types
    sent = json.loads(receiver.calls[0]["body"])["data"]["email"]
    assert sent["campaign_id"] == campaign_id
    assert sent["status"] == "sent"
