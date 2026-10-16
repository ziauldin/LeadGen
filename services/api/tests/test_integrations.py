import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.crm import Deal, DealStage
from app.models.integration import IntegrationConnection, IntegrationLink
from app.models.user import User
from app.models.workspace import Workspace
from app.services.integrations import clients
from app.services.integrations import service as integrations
from app.workers.integration_jobs import pull_integration_statuses
from tests.conftest import TestingSessionLocal, auth_headers, get_client
from tests.sending_helpers import approved_message

TOKEN = "pd-token-0123456789"


class FakeCrm:
    """Pretends to be both HubSpot and Pipedrive; records every request."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict]] = []
        self.deal_status = "open"
        self.refuse = False
        self.next_id = 100

    def _id(self) -> int:
        self.next_id += 1
        return self.next_id

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = {}
        if request.content:
            try:
                body = json.loads(request.content)
            except ValueError:
                body = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        self.requests.append((request.method, request.url.host + request.url.path, body))
        if self.refuse:
            return httpx.Response(401, json={"error": "unauthorized"})
        host, path, method = request.url.host, request.url.path, request.method
        if host == "acme.pipedrive.com":
            assert request.headers["x-api-token"] == TOKEN
            if path == "/api/v1/users/me":
                return httpx.Response(
                    200, json={"success": True, "data": {"company_name": "Acme Ltd"}}
                )
            if path == "/api/v1/persons/search":
                return httpx.Response(200, json={"success": True, "data": {"items": []}})
            if path == "/api/v1/persons" and method == "POST":
                return httpx.Response(201, json={"success": True, "data": {"id": self._id()}})
            if path.startswith("/api/v1/persons/") and method == "PUT":
                return httpx.Response(
                    200, json={"success": True, "data": {"id": int(path.rsplit("/", 1)[1])}}
                )
            if path == "/api/v1/deals" and method == "POST":
                return httpx.Response(201, json={"success": True, "data": {"id": self._id()}})
            if path.startswith("/api/v1/deals/"):
                deal_id = int(path.rsplit("/", 1)[1])
                return httpx.Response(
                    200, json={"success": True, "data": {"id": deal_id, "status": self.deal_status}}
                )
        if host == "api.hubapi.com":
            if path == "/oauth/v1/token":
                return httpx.Response(
                    200,
                    json={
                        "access_token": f"at-{len(self.requests)}",
                        "refresh_token": "rt-1",
                        "expires_in": 1800,
                    },
                )
            assert request.headers["authorization"].startswith("Bearer at-")
            if path.startswith("/oauth/v1/access-tokens/"):
                return httpx.Response(200, json={"hub_domain": "acme.hubspot.com"})
            if path == "/crm/v3/objects/contacts/search":
                return httpx.Response(200, json={"results": []})
            if path == "/crm/v3/objects/contacts":
                return httpx.Response(201, json={"id": "c1"})
            if path.startswith("/crm/v3/objects/contacts/"):
                return httpx.Response(200, json={"id": path.rsplit("/", 1)[1]})
            if path == "/crm/v3/objects/deals":
                return httpx.Response(201, json={"id": "d1"})
            if path == "/crm/v3/objects/deals/batch/read":
                closed = self.deal_status != "open"
                won = self.deal_status == "won"
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "id": row["id"],
                                "properties": {
                                    "hs_is_closed": str(closed).lower(),
                                    "hs_is_closed_won": str(won).lower(),
                                },
                            }
                            for row in body["inputs"]
                        ]
                    },
                )
            if path.startswith("/crm/v3/objects/deals/"):
                return httpx.Response(200, json={"id": path.rsplit("/", 1)[1]})
        return httpx.Response(404, json={"error": f"unexpected {method} {host}{path}"})

    def calls(self, method: str, path: str) -> list[dict]:
        return [body for m, url, body in self.requests if m == method and url.endswith(path)]


@pytest.fixture
def fake(monkeypatch):
    crm = FakeCrm()
    monkeypatch.setattr(settings, "feature_integrations", True)
    monkeypatch.setattr(settings, "feature_crm", True)
    monkeypatch.setattr(
        clients, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(crm.handler))
    )
    return crm


def _plan(plan: str, email: str = "test@example.com") -> int:
    db = TestingSessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        workspace = db.get(Workspace, user.last_workspace_id)
        workspace.plan = plan
        db.commit()
        return workspace.id
    finally:
        db.close()


def _db():
    db = TestingSessionLocal()
    db.info["tenant_bypass"] = True
    return db


def _connect_pipedrive(client, headers):
    return client.post(
        "/integrations/pipedrive",
        headers=headers,
        json={"api_token": TOKEN, "company_domain": "https://acme.pipedrive.com/"},
    )


def test_flag_and_plan_gates(monkeypatch):
    client = get_client()
    headers = auth_headers(client)
    overview = client.get("/integrations", headers=headers).json()
    assert overview["enabled"] is False and overview["connections"] == []
    assert _connect_pipedrive(client, headers).status_code == 404

    monkeypatch.setattr(settings, "feature_integrations", True)
    refused = _connect_pipedrive(client, headers)
    assert refused.status_code == 403
    assert refused.json()["code"] == "plan_feature_required"


def test_pipedrive_connect_push_and_pull(fake):
    client = get_client()
    headers, campaign_id, _ids = approved_message(client)
    _plan("pro")
    bad = client.post(
        "/integrations/pipedrive",
        headers=headers,
        json={"api_token": TOKEN, "company_domain": "evil.example.com"},
    )
    assert bad.status_code == 400

    connected = _connect_pipedrive(client, headers)
    assert connected.status_code == 201, connected.text
    connection = connected.json()
    assert connection["account_label"] == "Acme Ltd" and connection["status"] == "active"
    assert connection["settings"] == {
        "push_contacts": True,
        "push_deals": True,
        "pull_status": True,
    }
    db = _db()
    try:
        stored = db.get(IntegrationConnection, connection["id"])
        assert TOKEN not in stored.config_encrypted
    finally:
        db.close()

    # The simulator's first reply is interested: a deal opens and both go to Pipedrive.
    client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers)
    client.post("/replies/sync", headers=headers)
    deal_body = fake.calls("POST", "/api/v1/deals")
    assert len(deal_body) == 1
    assert deal_body[0]["status"] == "open" and deal_body[0]["person_id"] == 101
    person = fake.calls("POST", "/api/v1/persons")
    assert person[0]["email"][0]["value"] == "alex@example-foods.co.uk"
    assert fake.calls("PUT", "/api/v1/persons/101")  # the reply's own contact push updates it

    db = _db()
    try:
        links = {link.object_type: link.remote_id for link in db.scalars(select(IntegrationLink))}
        assert links == {"contact": "101", "deal": "102"}
    finally:
        db.close()
    logs = client.get(f"/integrations/{connection['id']}/logs", headers=headers).json()
    assert {(row["object_type"], row["status"]) for row in logs} == {
        ("contact", "ok"),
        ("deal", "ok"),
    }

    # Won in Pipedrive: the local deal moves to Won.
    fake.deal_status = "won"
    assert pull_integration_statuses() == 1
    db = _db()
    try:
        deal = db.scalars(select(Deal)).one()
        assert db.get(DealStage, deal.stage_id).kind == "won" and deal.closed_at is not None
    finally:
        db.close()
    assert pull_integration_statuses() == 0  # nothing new

    # A revoked token marks the connection for reconnecting.
    fake.refuse = True
    client.post("/deals", headers=headers, json={"title": "Second deal"})
    overview = client.get("/integrations", headers=headers).json()
    row = overview["connections"][0]
    assert row["status"] == "error" and "Reconnect" in row["last_error"]
    assert client.post(f"/integrations/{row['id']}/sync", headers=headers).status_code == 400

    other = auth_headers(client, "other@example.com")
    assert client.get(f"/integrations/{row['id']}/logs", headers=other).status_code == 404
    assert client.delete(f"/integrations/{row['id']}", headers=other).status_code == 404
    assert client.delete(f"/integrations/{row['id']}", headers=headers).status_code == 204


def test_settings_turn_pushes_off(fake):
    client = get_client()
    headers = auth_headers(client)
    _plan("pro")
    connection = _connect_pipedrive(client, headers).json()
    updated = client.patch(
        f"/integrations/{connection['id']}", headers=headers, json={"push_deals": False}
    ).json()
    assert updated["settings"]["push_deals"] is False
    client.post("/deals", headers=headers, json={"title": "Not pushed"})
    assert fake.calls("POST", "/api/v1/deals") == []


def test_hubspot_oauth_and_deal_push(fake, monkeypatch):
    monkeypatch.setattr(settings, "hubspot_client_id", "hub-client")
    monkeypatch.setattr(settings, "hubspot_client_secret", "hub-secret")
    client = get_client()
    headers, _campaign, _ids = approved_message(client)
    workspace_id = _plan("enterprise")
    providers = {
        p["key"]: p for p in client.get("/integrations", headers=headers).json()["providers"]
    }
    assert providers["hubspot"]["available"] is True

    url = client.post("/integrations/hubspot/connect", headers=headers).json()["url"]
    query = parse_qs(urlparse(url).query)
    assert url.startswith("https://app.hubspot.com/oauth/authorize")
    assert "crm.objects.deals.write" in query["scope"][0]
    assert (
        client.get(
            "/integrations/oauth/hubspot/callback",
            params={"code": "c", "state": "forged"},
            follow_redirects=False,
        )
        .headers["location"]
        .endswith("integration=error&detail=This+connection+link+has+expired.+Please+try+again.")
    )
    done = client.get(
        "/integrations/oauth/hubspot/callback",
        params={"code": "auth-code", "state": query["state"][0]},
        follow_redirects=False,
    )
    assert done.status_code == 302 and done.headers["location"].endswith(
        "/settings/integrations?integration=connected"
    )
    assert fake.calls("POST", "/oauth/v1/token")[0]["grant_type"] == "authorization_code"
    connection = client.get("/integrations", headers=headers).json()["connections"][0]
    assert connection["provider"] == "hubspot" and connection["account_label"] == "acme.hubspot.com"

    lead_id = client.get("/leads", headers=headers).json()["items"][0]["id"]
    created = client.post(
        "/deals", headers=headers, json={"lead_id": lead_id, "value_cents": 120000}
    )
    assert created.status_code == 201
    deal = fake.calls("POST", "/crm/v3/objects/deals")[0]
    assert deal["properties"]["dealstage"] == "appointmentscheduled"
    assert deal["properties"]["amount"] == "1200.00"
    assert deal["associations"][0]["to"]["id"] == "c1"
    contact = fake.calls("POST", "/crm/v3/objects/contacts")[0]
    assert contact["properties"]["email"] == "alex@example-foods.co.uk"
    assert contact["properties"]["firstname"] == "Person"

    # Expired access token: refreshed with the refresh token and stored again.
    db = _db()
    try:
        row = db.scalar(
            select(IntegrationConnection).where(IntegrationConnection.workspace_id == workspace_id)
        )
        config = integrations._config(row)
        config["expires_at"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
        integrations._store(row, config)
        db.commit()
    finally:
        db.close()
    fake.deal_status = "lost"
    assert pull_integration_statuses() == 1
    assert fake.calls("POST", "/oauth/v1/token")[-1]["grant_type"] == "refresh_token"
    db = _db()
    try:
        row = db.scalar(
            select(IntegrationConnection).where(IntegrationConnection.workspace_id == workspace_id)
        )
        assert datetime.fromisoformat(integrations._config(row)["expires_at"]) > datetime.now(UTC)
    finally:
        db.close()
