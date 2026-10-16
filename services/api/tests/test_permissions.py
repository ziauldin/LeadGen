import csv
import io
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.permissions import (
    ADMIN_PERMISSIONS,
    ALL_PERMISSIONS,
    MEMBER_PERMISSIONS,
    permissions_for,
)
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.workspace import Workspace
from app.services.audit.retention import purge_audit_logs
from tests.conftest import TestingSessionLocal, auth_headers, get_client

OWNER = "owner@example.com"
MEMBER = "member@example.com"
ADMIN = "admin@example.com"
NICHE = {"name": "Dentists", "country": "UK", "industry": "Dental"}


def _join(client, owner, email, role="member"):
    from app.services.platform_email.mailer import OUTBOX

    assert (
        client.post(
            "/workspaces/current/invitations", headers=owner, json={"email": email, "role": role}
        ).status_code
        == 201
    )
    token = next(
        m.text.split("/invite/")[1].split()[0]
        for m in reversed(OUTBOX)
        if m.to == email and m.tags.get("kind") == "invite"
    )
    headers = auth_headers(client, email)
    workspace_id = client.post(f"/invitations/{token}/accept", headers=headers).json()["id"]
    return {**headers, "X-Workspace-Id": str(workspace_id)}


def _user_id(email):
    db = TestingSessionLocal()
    try:
        return db.scalar(select(User.id).where(User.email == email))
    finally:
        db.close()


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


def test_built_in_roles_map_to_permission_sets():
    assert permissions_for("owner") == ALL_PERMISSIONS
    assert permissions_for("admin") == ADMIN_PERMISSIONS
    assert "billing.manage" not in ADMIN_PERMISSIONS
    assert permissions_for("member") == MEMBER_PERMISSIONS
    # Custom permissions apply to members only and drop unknown values.
    assert permissions_for("member", ["leads.write", "nope"]) == frozenset({"leads.write"})
    assert permissions_for("admin", []) == ADMIN_PERMISSIONS


def test_permissions_endpoint_and_route_enforcement():
    client = get_client()
    owner = auth_headers(client, OWNER)
    _set_plan(OWNER, "pro")
    member = _join(client, owner, MEMBER)
    admin = _join(client, owner, ADMIN, role="admin")

    mine = client.get("/workspaces/current/permissions", headers=member).json()
    assert mine["role"] == "member"
    assert "leads.write" in mine["permissions"]
    assert "members.manage" not in mine["permissions"]

    # Members work with leads but can't change settings, invite or read the audit log.
    assert client.post("/niches", headers=member, json=NICHE).status_code == 201
    assert (
        client.patch("/workspaces/current", headers=member, json={"name": "X"}).status_code == 403
    )
    assert client.get("/audit-logs", headers=member).status_code == 403
    denied = client.post(
        "/workspaces/current/invitations",
        headers=member,
        json={"email": "x@example.com", "role": "member"},
    )
    assert denied.status_code == 403
    assert "Invite people" in denied.json()["detail"]

    # Admins can see the audit log but not billing.
    assert client.get("/audit-logs", headers=admin).status_code == 200
    assert (
        "billing.manage"
        not in client.get("/workspaces/current/permissions", headers=admin).json()["permissions"]
    )

    listing = client.get("/roles", headers=member).json()
    assert [r["name"] for r in listing] == ["Owner", "Admin", "Member"]
    assert len(client.get("/roles/permissions", headers=member).json()) == len(ALL_PERMISSIONS)


def test_custom_roles_need_the_enterprise_plan():
    client = get_client()
    owner = auth_headers(client, OWNER)
    response = client.post("/roles", headers=owner, json={"name": "Viewer", "permissions": []})
    assert response.status_code == 403
    assert response.json()["code"] == "plan_feature_required"


def test_custom_role_lifecycle():
    client = get_client()
    owner = auth_headers(client, OWNER)
    _set_plan(OWNER, "pro")
    member = _join(client, owner, MEMBER)
    admin = _join(client, owner, ADMIN, role="admin")
    _set_plan(OWNER, "enterprise")
    member_id = _user_id(MEMBER)
    admin_id = _user_id(ADMIN)

    viewer = client.post(
        "/roles",
        headers=owner,
        json={"name": "Viewer", "description": "Read only", "permissions": []},
    )
    assert viewer.status_code == 201, viewer.text
    viewer_id = viewer.json()["id"]
    assert (
        client.post("/roles", headers=owner, json={"name": "Viewer", "permissions": []}).status_code
        == 409
    )
    assert (
        client.post(
            "/roles", headers=owner, json={"name": "Bad", "permissions": ["nope"]}
        ).status_code
        == 400
    )
    # Admins can't hand out a permission they don't have.
    escalate = client.post(
        "/roles", headers=admin, json={"name": "Payer", "permissions": ["billing.manage"]}
    )
    assert escalate.status_code == 403

    assigned = client.patch(
        f"/workspaces/current/members/{member_id}",
        headers=owner,
        json={"custom_role_id": viewer_id},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["custom_role"] == "Viewer"
    assert assigned.json()["role"] == "member"
    assert client.get("/workspaces/current/permissions", headers=member).json() == {
        "role": "member",
        "custom_role": "Viewer",
        "permissions": [],
    }
    assert client.post("/niches", headers=member, json=NICHE).status_code == 403
    assert client.get("/niches", headers=member).status_code == 200

    # Custom roles only apply to the member role.
    to_admin = client.patch(
        f"/workspaces/current/members/{admin_id}", headers=owner, json={"custom_role_id": viewer_id}
    )
    assert to_admin.status_code == 400

    # Editing the role changes what its members can do straight away.
    updated = client.patch(
        f"/roles/{viewer_id}",
        headers=owner,
        json={"name": "Researcher", "permissions": ["leads.write"]},
    )
    assert updated.status_code == 200
    assert client.post("/niches", headers=member, json=NICHE).status_code == 201
    roles = {r["name"]: r for r in client.get("/roles", headers=owner).json()}
    assert roles["Researcher"]["member_count"] == 1

    # Deleting it puts the member back on the built-in set.
    assert client.delete(f"/roles/{viewer_id}", headers=owner).status_code == 204
    after = client.get("/workspaces/current/permissions", headers=member).json()
    assert after["custom_role"] is None
    assert set(after["permissions"]) == set(MEMBER_PERMISSIONS)

    actions = [e["action"] for e in client.get("/audit-logs", headers=owner).json()["items"]]
    assert {"role.created", "role.updated", "role.deleted", "member_custom_role_changed"} <= set(
        actions
    )


def test_roles_are_private_to_their_workspace():
    client = get_client()
    owner = auth_headers(client, OWNER)
    _set_plan(OWNER, "enterprise")
    role_id = client.post(
        "/roles", headers=owner, json={"name": "Viewer", "permissions": []}
    ).json()["id"]

    other = auth_headers(client, "other@example.com")
    _set_plan("other@example.com", "enterprise")
    assert (
        client.patch(f"/roles/{role_id}", headers=other, json={"name": "Mine"}).status_code == 404
    )
    assert client.delete(f"/roles/{role_id}", headers=other).status_code == 404
    assert "Viewer" not in [r["name"] for r in client.get("/roles", headers=other).json()]
    member_id = _user_id("other@example.com")
    stolen = client.patch(
        f"/workspaces/current/members/{member_id}", headers=other, json={"custom_role_id": role_id}
    )
    assert stolen.status_code == 404


def test_audit_log_filters_export_and_retention():
    client = get_client()
    owner = auth_headers(client, OWNER)
    workspace_id = _set_plan(OWNER, "free")
    client.patch("/workspaces/current", headers=owner, json={"name": "Renamed"})
    old_time = datetime.now(UTC) - timedelta(days=45)
    db = TestingSessionLocal()
    try:
        db.add(
            AuditLog(
                workspace_id=workspace_id, action="old.thing", entity_type="x", created_at=old_time
            )
        )
        db.commit()
    finally:
        db.close()

    page = client.get("/audit-logs", headers=owner).json()
    assert page["retention_days"] == 30
    actions = [e["action"] for e in page["items"]]
    assert "old.thing" not in actions  # outside the free plan's window
    assert page["total"] == len(page["items"]) >= 1

    filtered = client.get("/audit-logs", headers=owner, params={"action": "workspace"}).json()
    assert all(e["action"].startswith("workspace") for e in filtered["items"])

    exported = client.get("/audit-logs/export", headers=owner)
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(exported.text)))
    assert rows[0] == ["time", "actor", "action", "entity_type", "entity_id", "details"]
    assert len(rows) == len(page["items"]) + 1

    # Enterprise keeps two years, so the same entry is visible there.
    _set_plan(OWNER, "enterprise")
    assert "old.thing" in [
        e["action"] for e in client.get("/audit-logs", headers=owner).json()["items"]
    ]

    # The daily purge applies the plan's window.
    _set_plan(OWNER, "free")
    db = TestingSessionLocal()
    try:
        assert purge_audit_logs(db) >= 1
        remaining = db.scalars(
            select(AuditLog.action).where(AuditLog.workspace_id == workspace_id)
        ).all()
        assert "old.thing" not in remaining
        assert remaining
    finally:
        db.close()
