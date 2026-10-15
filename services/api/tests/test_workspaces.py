from datetime import UTC, datetime, timedelta

from app.models.workspace import WorkspaceInvitation
from tests.conftest import TestingSessionLocal, auth_headers, get_client, register_user

OWNER = "owner@example.com"
INVITEE = "invitee@example.com"


def _invite(client, headers, email=INVITEE, role="member"):
    return client.post(
        "/workspaces/current/invitations",
        headers=headers,
        json={"email": email, "role": role},
    )


def _invite_token(email=INVITEE) -> str:
    from app.services.platform_email.mailer import OUTBOX

    for message in reversed(OUTBOX):
        if message.to == email and message.tags.get("kind") == "invite":
            return message.text.split("/invite/")[1].split()[0]
    raise AssertionError("no invite email")


def test_registration_creates_personal_workspace_as_owner():
    client = get_client()
    headers = auth_headers(client, OWNER)
    current = client.get("/workspaces/current", headers=headers).json()
    assert current["role"] == "owner"
    assert current["name"].endswith("workspace")
    listing = client.get("/workspaces", headers=headers).json()
    assert len(listing["items"]) == 1
    assert listing["current_workspace_id"] == current["id"]


def test_invite_accept_and_member_access():
    client = get_client()
    owner = auth_headers(client, OWNER)
    workspace_id = client.get("/workspaces/current", headers=owner).json()["id"]
    client.post(
        "/niches",
        headers=owner,
        json={"name": "Shared", "country": "UK", "industry": "Legal"},
    )

    assert _invite(client, owner).status_code == 201
    token = _invite_token()
    preview = client.get(f"/invitations/{token}").json()
    assert preview["email"] == INVITEE

    invitee = auth_headers(client, INVITEE)
    accepted = client.post(f"/invitations/{token}/accept", headers=invitee)
    assert accepted.status_code == 200
    assert accepted.json()["id"] == workspace_id

    niches = client.get(
        "/niches",
        headers={**invitee, "X-Workspace-Id": str(workspace_id)},
    ).json()
    assert [n["name"] for n in niches["items"]] == ["Shared"]

    # Invitations are single use.
    assert client.post(f"/invitations/{token}/accept", headers=invitee).status_code == 404


def test_invitation_for_other_email_cannot_be_accepted():
    client = get_client()
    owner = auth_headers(client, OWNER)
    _invite(client, owner)
    token = _invite_token()
    other = auth_headers(client, "someone-else@example.com")
    assert client.post(f"/invitations/{token}/accept", headers=other).status_code == 403


def test_expired_and_revoked_invitations_fail():
    client = get_client()
    owner = auth_headers(client, OWNER)
    invitation_id = _invite(client, owner).json()["id"]
    token = _invite_token()

    db = TestingSessionLocal()
    try:
        invitation = db.get(WorkspaceInvitation, invitation_id)
        invitation.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()
    assert client.get(f"/invitations/{token}").status_code == 404

    second_id = _invite(client, owner, email="later@example.com").json()["id"]
    second_token = _invite_token("later@example.com")
    assert (
        client.delete(f"/workspaces/current/invitations/{second_id}", headers=owner).status_code
        == 204
    )
    assert client.get(f"/invitations/{second_token}").status_code == 404


def test_members_cannot_manage_providers_or_members():
    client = get_client()
    owner = auth_headers(client, OWNER)
    workspace_id = client.get("/workspaces/current", headers=owner).json()["id"]
    _invite(client, owner)
    invitee = auth_headers(client, INVITEE)
    client.post(f"/invitations/{_invite_token()}/accept", headers=invitee)
    member = {**invitee, "X-Workspace-Id": str(workspace_id)}

    forbidden = [
        client.post(
            "/provider-settings",
            headers=member,
            json={"provider_type": "search", "provider_name": "bing", "config": {"api_key": "k"}},
        ),
        client.post(
            "/workspaces/current/invitations",
            headers=member,
            json={"email": "x@example.com"},
        ),
        client.patch("/settings", headers=member, json={"sender_name": "x"}),
        client.patch(
            f"/workspaces/current/members/{client.get('/auth/me', headers=owner).json()['id']}",
            headers=member,
            json={"role": "member"},
        ),
    ]
    assert all(response.status_code == 403 for response in forbidden), [
        r.status_code for r in forbidden
    ]


def test_last_owner_cannot_be_demoted_or_removed():
    client = get_client()
    owner = auth_headers(client, OWNER)
    owner_id = client.get("/auth/me", headers=owner).json()["id"]
    demote = client.patch(
        f"/workspaces/current/members/{owner_id}",
        headers=owner,
        json={"role": "admin"},
    )
    assert demote.status_code == 400
    leave = client.post("/workspaces/current/leave", headers=owner)
    assert leave.status_code == 400


def test_admin_cannot_grant_owner():
    client = get_client()
    owner = auth_headers(client, OWNER)
    workspace_id = client.get("/workspaces/current", headers=owner).json()["id"]
    _invite(client, owner, role="admin")
    admin = auth_headers(client, INVITEE)
    client.post(f"/invitations/{_invite_token()}/accept", headers=admin)
    admin_ws = {**admin, "X-Workspace-Id": str(workspace_id)}
    admin_id = client.get("/auth/me", headers=admin).json()["id"]
    response = client.patch(
        f"/workspaces/current/members/{admin_id}",
        headers=admin_ws,
        json={"role": "owner"},
    )
    assert response.status_code == 403


def test_switching_workspaces_changes_default_scope():
    client = get_client()
    headers = auth_headers(client, OWNER)
    first = client.get("/workspaces/current", headers=headers).json()["id"]
    second = client.post("/workspaces", headers=headers, json={"name": "Second"}).json()["id"]

    client.post(f"/workspaces/{second}/switch", headers=headers)
    assert client.get("/workspaces/current", headers=headers).json()["id"] == second
    client.post(
        "/niches",
        headers=headers,
        json={"name": "Only in second", "country": "UK", "industry": "Legal"},
    )
    client.post(f"/workspaces/{first}/switch", headers=headers)
    assert client.get("/niches", headers=headers).json()["total"] == 0
    assert client.post("/workspaces/999999/switch", headers=headers).status_code == 404


def test_unverified_user_cannot_invite():
    client = get_client()
    register_user(client, OWNER, verify=False)
    from tests.conftest import login

    headers = login(client, OWNER)
    assert _invite(client, headers).status_code == 403


def test_onboarding_status_reflects_progress():
    client = get_client()
    headers = auth_headers(client, OWNER)
    status = client.get("/workspaces/current/onboarding", headers=headers).json()
    assert status["email_verified"] is True
    assert status["niche_created"] is False
    assert status["completed"] is False
    client.post("/niches", headers=headers, json={"name": "N", "country": "UK", "industry": "L"})
    assert client.get("/workspaces/current/onboarding", headers=headers).json()["niche_created"]
