import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.flags import feature_enabled
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.workspace import Workspace
from scripts.manage_superusers import main as manage_superusers
from tests.conftest import TestingSessionLocal, auth_headers, get_client, login

ADMIN = "ops@example.com"
CUSTOMER = "customer@example.com"
NICHE = {"name": "Dentists", "country": "UK", "industry": "Dental"}


@pytest.fixture(autouse=True)
def no_admin_mfa(monkeypatch):
    monkeypatch.setattr(settings, "superuser_require_mfa", False)


def _admin(client):
    auth_headers(client, ADMIN)
    assert manage_superusers(["grant", ADMIN]) == 0
    return login(client, ADMIN)  # the token version changed


def _customer(client):
    headers = auth_headers(client, CUSTOMER)
    client.post("/niches", headers=headers, json=NICHE)
    db = TestingSessionLocal()
    try:
        workspace_id = db.scalar(select(User).where(User.email == CUSTOMER)).last_workspace_id
    finally:
        db.close()
    return headers, workspace_id


def test_admin_area_is_hidden_from_customers():
    client = get_client()
    headers, _ = _customer(client)
    assert client.get("/admin/overview", headers=headers).status_code == 404
    assert client.get("/admin/workspaces", headers=headers).status_code == 404
    assert client.get("/admin/overview").status_code == 401


def test_superusers_need_two_factor(monkeypatch):
    client = get_client()
    admin = _admin(client)
    monkeypatch.setattr(settings, "superuser_require_mfa", True)
    response = client.get("/admin/overview", headers=admin)
    assert response.status_code == 403
    assert response.json()["code"] == "mfa_required"


def test_cli_grants_and_revokes():
    client = get_client()
    admin = _admin(client)
    assert client.get("/auth/me", headers=admin).json()["is_superuser"] is True
    assert manage_superusers(["revoke", ADMIN]) == 0
    assert client.get("/admin/overview", headers=login(client, ADMIN)).status_code == 404
    assert manage_superusers(["grant", "nobody@example.com"]) == 1


def test_overview_workspaces_and_plan_changes():
    client = get_client()
    _, workspace_id = _customer(client)
    admin = _admin(client)

    overview = client.get("/admin/overview", headers=admin).json()
    assert overview["users"] == 2
    assert overview["workspaces"] == 2

    listing = client.get("/admin/workspaces", headers=admin, params={"search": CUSTOMER}).json()
    assert [w["id"] for w in listing["items"]] == [workspace_id]
    assert listing["items"][0]["owner_email"] == CUSTOMER

    updated = client.patch(
        f"/admin/workspaces/{workspace_id}",
        headers=admin,
        json={
            "plan": "pro",
            "plan_overrides": {"monthly_sends": 75000, "features": {"custom_roles": True}},
            "feature_flags": {"public_api": True},
            "note": "Pilot customer",
        },
    )
    assert updated.status_code == 200, updated.text
    detail = updated.json()
    assert detail["plan"] == "pro"
    assert detail["limits"]["monthly_sends"] == 75000
    assert detail["features"]["custom_roles"] is True
    assert detail["effective_flags"]["public_api"] is True
    assert detail["members_list"][0]["email"] == CUSTOMER

    bad = client.patch(
        f"/admin/workspaces/{workspace_id}", headers=admin, json={"plan_overrides": {"bogus": 1}}
    )
    assert bad.status_code == 400
    assert (
        client.patch(
            f"/admin/workspaces/{workspace_id}", headers=admin, json={"plan": "platinum"}
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/admin/workspaces/{workspace_id}",
            headers=admin,
            json={"feature_flags": {"nope": True}},
        ).status_code
        == 400
    )

    # Clearing a flag falls back to the global setting.
    cleared = client.patch(
        f"/admin/workspaces/{workspace_id}",
        headers=admin,
        json={"feature_flags": {"public_api": None}},
    )
    assert cleared.json()["feature_flags"] is None
    db = TestingSessionLocal()
    try:
        assert (
            feature_enabled("public_api", db.get(Workspace, workspace_id))
            is settings.feature_public_api
        )
    finally:
        db.close()


def test_suspend_and_resume_sending():
    client = get_client()
    customer, workspace_id = _customer(client)
    admin = _admin(client)
    suspended = client.post(
        f"/admin/workspaces/{workspace_id}/suspend",
        headers=admin,
        json={"reason": "Complaint spike"},
    )
    assert suspended.json()["sending_suspended_reason"] == "Complaint spike"
    assert (
        client.get("/admin/workspaces", headers=admin, params={"suspended": True}).json()["total"]
        == 1
    )
    resumed = client.post(f"/admin/workspaces/{workspace_id}/unsuspend", headers=admin)
    assert resumed.json()["sending_suspended_at"] is None

    # The customer sees the admin actions in their own audit log.
    actions = [e["action"] for e in client.get("/audit-logs", headers=customer).json()["items"]]
    assert "admin.sending_suspended" in actions and "admin.sending_resumed" in actions


def test_read_only_impersonation():
    client = get_client()
    _customer_headers, workspace_id = _customer(client)
    admin = _admin(client)
    assert (
        client.post(
            f"/admin/workspaces/{workspace_id}/impersonate", headers=admin, json={"reason": "x"}
        ).status_code
        == 422
    )
    session = client.post(
        f"/admin/workspaces/{workspace_id}/impersonate",
        headers=admin,
        json={"reason": "Ticket #123: campaign not sending"},
    ).json()
    assert session["read_only"] is True
    assert session["user_email"] == CUSTOMER
    viewer = {"Authorization": f"Bearer {session['access_token']}"}

    me = client.get("/auth/me", headers=viewer).json()
    assert me["email"] == CUSTOMER
    assert me["impersonation"]["admin_email"] == ADMIN
    assert me["impersonation"]["read_only"] is True
    assert client.get("/niches", headers=viewer).json()["total"] == 1

    blocked = client.post("/niches", headers=viewer, json={**NICHE, "name": "Other"})
    assert blocked.status_code == 403
    assert "read-only" in blocked.json()["detail"]
    # The impersonation token can't reach the admin area.
    assert client.get("/admin/overview", headers=viewer).status_code == 404

    db = TestingSessionLocal()
    try:
        log = db.scalar(select(AuditLog).where(AuditLog.action == "admin.impersonation_started"))
        assert log.workspace_id == workspace_id
        assert log.metadata_["reason"].startswith("Ticket #123")
    finally:
        db.close()

    # Revoking the admin's superuser ends the session.
    manage_superusers(["revoke", ADMIN])
    assert client.get("/auth/me", headers=viewer).status_code == 401


def test_write_impersonation_still_protects_account_security():
    client = get_client()
    _, workspace_id = _customer(client)
    admin = _admin(client)
    session = client.post(
        f"/admin/workspaces/{workspace_id}/impersonate",
        headers=admin,
        json={"reason": "Fixing a broken campaign with the customer", "write": True, "minutes": 15},
    ).json()
    viewer = {"Authorization": f"Bearer {session['access_token']}"}
    assert (
        client.post("/niches", headers=viewer, json={**NICHE, "name": "Fixed"}).status_code == 201
    )
    assert (
        client.post(
            "/auth/change-password",
            headers=viewer,
            json={"current_password": "testpass12", "new_password": "another-pass-99"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api-keys", headers=viewer, json={"name": "x", "scopes": ["leads:read"]}
        ).status_code
        == 403
    )
    assert client.delete("/auth/account", headers=viewer).status_code == 403


def test_users_suppressions_abuse_and_health():
    client = get_client()
    customer, _ = _customer(client)
    admin = _admin(client)
    users = client.get("/admin/users", headers=admin, params={"search": "customer"}).json()
    assert users["total"] == 1
    customer_id = users["items"][0]["id"]

    assert client.post(f"/admin/users/{customer_id}/disable", headers=admin).json() == {
        "is_active": False
    }
    assert client.get("/auth/me", headers=customer).status_code == 401
    assert client.post(f"/admin/users/{customer_id}/enable", headers=admin).json() == {
        "is_active": True
    }
    admin_id = client.get("/auth/me", headers=admin).json()["id"]
    assert client.post(f"/admin/users/{admin_id}/disable", headers=admin).status_code == 400

    created = client.post(
        "/admin/suppressions",
        headers=admin,
        json={"email": "Spamtrap@Example.org", "reason": "Known trap"},
    )
    assert created.status_code == 201
    assert created.json()["email"] == "spamtrap@example.org"
    assert len(client.get("/admin/suppressions", headers=admin).json()) == 1
    assert (
        client.delete(f"/admin/suppressions/{created.json()['id']}", headers=admin).status_code
        == 204
    )

    abuse = client.get("/admin/abuse", headers=admin).json()
    assert abuse == {"sending": [], "signups": []}
    health = client.get("/admin/health", headers=admin).json()
    assert health["checks"]["database"]["ok"] is True
    assert "webhooks_pending" in health

    trail = [row["action"] for row in client.get("/admin/audit-logs", headers=admin).json()]
    assert "admin.user_disabled" in trail and "admin.global_suppression_added" in trail
    assert "admin.superuser_granted" in trail


def test_abuse_queue_flags_high_bounce_workspaces():
    from datetime import UTC, datetime

    from tests.sending_helpers import approved_message

    client = get_client()
    _headers, _campaign_id, message_ids = approved_message(
        client, emails=tuple(f"person{i}@example-foods.co.uk" for i in range(20))
    )
    admin = _admin(client)
    db = TestingSessionLocal()
    try:
        from app.models.email_message import EmailMessage

        for index, message_id in enumerate(message_ids):
            message = db.get(EmailMessage, message_id)
            message.status = "bounced" if index < 3 else "sent"
            message.sent_at = datetime.now(UTC)
        db.commit()
    finally:
        db.close()
    abuse = client.get("/admin/abuse", headers=admin).json()
    assert len(abuse["sending"]) == 1
    assert abuse["sending"][0]["bounced_7d"] == 3
    assert "Bounce rate" in abuse["sending"][0]["reasons"][0]
