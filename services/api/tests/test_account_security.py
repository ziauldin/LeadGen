import httpx
import pyotp
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.auth import protection
from tests.conftest import auth_headers, get_client, login, register_user
from tests.test_workspaces import _invite_token

EMAIL = "secure@acme-test.co.uk"
PASSWORD = "testpass12"
XRW = {"X-Requested-With": "fetch"}


def _enable_2fa(client, headers) -> tuple[str, list[str]]:
    setup = client.post("/auth/2fa/setup", headers=headers).json()
    assert setup["qr_code"].startswith("data:image/svg+xml;base64,")
    assert setup["otpauth_uri"].startswith("otpauth://totp/LeadsGen:")
    code = pyotp.TOTP(setup["secret"]).now()
    enabled = client.post("/auth/2fa/enable", headers=headers, json={"code": code})
    assert enabled.status_code == 200, enabled.text
    return setup["secret"], enabled.json()["recovery_codes"]


def _next_code(secret: str) -> str:
    """The next 30-second code: enabling already used the current one (no replays)."""
    import time

    return pyotp.TOTP(secret).at(time.time() + 30)


# --- two-factor ---------------------------------------------------------------------------------


def test_two_factor_login_with_code_and_recovery_code():
    client = get_client()
    headers = auth_headers(client, EMAIL)
    secret, recovery = _enable_2fa(client, headers)
    assert len(recovery) == 10
    assert client.get("/auth/me", headers=headers).json()["mfa_enabled"] is True

    first = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()
    assert first["mfa_required"] is True and first["access_token"] is None
    wrong = client.post("/auth/login/2fa", json={"mfa_token": first["mfa_token"], "code": "000000"})
    assert wrong.status_code == 401

    ok = client.post(
        "/auth/login/2fa",
        json={"mfa_token": first["mfa_token"], "code": _next_code(secret)},
    )
    assert ok.status_code == 200 and ok.json()["access_token"]

    # A recovery code works once.
    again = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()
    used = client.post(
        "/auth/login/2fa", json={"mfa_token": again["mfa_token"], "code": recovery[0]}
    )
    assert used.status_code == 200
    again = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()
    reused = client.post(
        "/auth/login/2fa", json={"mfa_token": again["mfa_token"], "code": recovery[0]}
    )
    assert reused.status_code == 401
    status = client.get("/auth/2fa", headers=headers).json()
    assert status == {"enabled": True, "recovery_codes_left": 9}


def test_mfa_token_cannot_be_used_as_an_access_token():
    client = get_client()
    headers = auth_headers(client, EMAIL)
    _enable_2fa(client, headers)
    first = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {first['mfa_token']}"})
    assert response.status_code == 401


def test_disable_needs_password_and_code():
    client = get_client()
    headers = auth_headers(client, EMAIL)
    secret, _ = _enable_2fa(client, headers)
    bad = client.post(
        "/auth/2fa/disable", headers=headers, json={"password": "nope", "code": "123456"}
    )
    assert bad.status_code == 401
    ok = client.post(
        "/auth/2fa/disable",
        headers=headers,
        json={"password": PASSWORD, "code": _next_code(secret)},
    )
    assert ok.status_code == 200
    plain = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()
    assert plain["access_token"] and not plain["mfa_required"]


# --- sessions and password ----------------------------------------------------------------------


def test_sessions_can_be_listed_and_revoked():
    laptop = get_client()
    register_user(laptop, EMAIL)
    headers = login(laptop, EMAIL)
    phone = TestClient(app)
    login(phone, EMAIL)

    sessions = laptop.get("/auth/sessions", headers=headers).json()
    assert len(sessions) == 2
    current = [s for s in sessions if s["current"]]
    other = [s for s in sessions if not s["current"]]
    assert len(current) == 1 and len(other) == 1

    assert laptop.delete(f"/auth/sessions/{other[0]['id']}", headers=headers).status_code == 204
    assert phone.post("/auth/refresh", headers=XRW).status_code == 401
    assert laptop.post("/auth/refresh", headers=XRW).status_code == 200
    assert laptop.delete("/auth/sessions/not-mine", headers=headers).status_code == 404


def test_change_password_signs_out_other_devices():
    laptop = get_client()
    register_user(laptop, EMAIL)
    headers = login(laptop, EMAIL)
    phone = TestClient(app)
    login(phone, EMAIL)

    wrong = laptop.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "nope", "new_password": "a-brand-new-pass"},
    )
    assert wrong.status_code == 401
    changed = laptop.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "a-brand-new-pass"},
    )
    assert changed.status_code == 200 and changed.json()["access_token"]
    assert phone.post("/auth/refresh", headers=XRW).status_code == 401
    assert laptop.post("/auth/refresh", headers=XRW).status_code == 200
    assert (
        laptop.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 401
    )
    login(laptop, EMAIL, "a-brand-new-pass")


# --- breached passwords and CAPTCHA -------------------------------------------------------------


def test_breach_count_uses_k_anonymity():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        # SHA-1("password") = 5BAA6 1E4C9B93F3F0682250B6CF8331B7EE68FD8
        return httpx.Response(200, text="1E4C9B93F3F0682250B6CF8331B7EE68FD8:3861493\r\nABC:1")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert protection.breach_count("password", client=client) == 3861493
    assert seen["url"].endswith("/range/5BAA6")
    assert protection.breach_count("unique-and-long-passphrase", client=client) == 0


def test_breached_password_is_rejected_on_sign_up(monkeypatch):
    monkeypatch.setattr(settings, "password_breach_check", True)
    monkeypatch.setattr(protection, "breach_count", lambda password, **_: 12)
    response = get_client().post(
        "/auth/register",
        json={"name": "X", "email": "breach@acme-test.co.uk", "password": "password123"},
    )
    assert response.status_code == 400
    assert "data breach" in response.json()["detail"]


def test_captcha_required_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "turnstile_secret_key", "turnstile-secret")
    client = get_client()
    missing = client.post(
        "/auth/register",
        json={"name": "X", "email": "bot@acme-test.co.uk", "password": "longpass123"},
    )
    assert missing.status_code == 400
    assert missing.json()["code"] == "captcha_required"

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        return httpx.Response(200, json={"success": "response=good" in body})

    mock = httpx.Client(transport=httpx.MockTransport(handler))
    protection.verify_captcha("good", client=mock)
    with pytest.raises(Exception, match="security check failed"):
        protection.verify_captcha("bad", client=mock)


def test_login_needs_captcha_after_repeated_failures(monkeypatch):
    client = get_client()
    register_user(client, EMAIL)
    for _ in range(3):
        client.post("/auth/login", json={"email": EMAIL, "password": "wrong-pass"})
    monkeypatch.setattr(settings, "turnstile_secret_key", "turnstile-secret")
    blocked = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "captcha_required"


# --- account deletion ---------------------------------------------------------------------------


def test_delete_account_removes_solo_workspace():
    client = get_client()
    headers = auth_headers(client, EMAIL)
    assert (
        client.request(
            "DELETE", "/auth/account", headers=headers, json={"password": "wrong-pass"}
        ).status_code
        == 401
    )
    deleted = client.request(
        "DELETE", "/auth/account", headers=headers, json={"password": PASSWORD}
    )
    assert deleted.status_code == 204
    assert (
        client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 401
    )


def test_sole_owner_with_members_cannot_delete_account():
    client = get_client()
    owner = auth_headers(client, EMAIL)
    invite = client.post(
        "/workspaces/current/invitations",
        headers=owner,
        json={"email": "teammate@acme-test.co.uk", "role": "member"},
    )
    assert invite.status_code == 201, invite.text
    token = _invite_token("teammate@acme-test.co.uk")
    mate = auth_headers(client, "teammate@acme-test.co.uk")
    assert client.post(f"/invitations/{token}/accept", headers=mate).status_code == 200

    blocked = client.request("DELETE", "/auth/account", headers=owner, json={"password": PASSWORD})
    assert blocked.status_code == 400
    assert "only owner" in blocked.json()["detail"]


# --- workspace two-factor policy ----------------------------------------------------------------


def test_workspace_can_require_two_factor():
    client = get_client()
    owner = auth_headers(client, EMAIL)
    refused = client.patch("/workspaces/current", headers=owner, json={"require_2fa": True})
    assert refused.status_code == 400  # owner must turn it on for themselves first
    _enable_2fa(client, owner)
    turned_on = client.patch("/workspaces/current", headers=owner, json={"require_2fa": True})
    assert turned_on.status_code == 200 and turned_on.json()["require_2fa"] is True
    assert client.get("/leads", headers=owner).status_code == 200

    invite = client.post(
        "/workspaces/current/invitations",
        headers=owner,
        json={"email": "nomfa@acme-test.co.uk", "role": "member"},
    )
    token = _invite_token("nomfa@acme-test.co.uk")
    member = auth_headers(client, "nomfa@acme-test.co.uk")
    workspace_id = turned_on.json()["id"]
    assert client.post(f"/invitations/{token}/accept", headers=member).status_code == 200
    blocked = client.get("/leads", headers={**member, "X-Workspace-Id": str(workspace_id)})
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "mfa_required"
    assert invite.status_code == 201


def test_a_code_cannot_be_replayed():
    client = get_client()
    headers = auth_headers(client, EMAIL)
    secret, _ = _enable_2fa(client, headers)
    import time as _time

    future = pyotp.TOTP(secret).at(_time.time() + 30)  # next step: allowed once
    first = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()
    assert (
        client.post(
            "/auth/login/2fa", json={"mfa_token": first["mfa_token"], "code": future}
        ).status_code
        == 200
    )
    again = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()
    replay = client.post("/auth/login/2fa", json={"mfa_token": again["mfa_token"], "code": future})
    assert replay.status_code == 401
