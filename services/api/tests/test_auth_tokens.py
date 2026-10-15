from datetime import timedelta

from app.core.config import settings
from app.core.security import create_access_token
from tests.conftest import auth_headers, get_client, latest_email_token, login, register_user

EMAIL = "owner@example.com"
PASSWORD = "correct-horse-42"
XRW = {"X-Requested-With": "fetch"}


def _login_body(client, email=EMAIL, password=PASSWORD):
    response = client.post(
        "/auth/login?delivery=body",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_login_sets_httponly_refresh_cookie():
    client = get_client()
    register_user(client, EMAIL, PASSWORD)
    response = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 200
    assert "refresh_token" not in response.json() or response.json()["refresh_token"] is None
    cookie = response.headers["set-cookie"]
    assert settings.refresh_cookie_name in cookie
    assert "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()


def test_cookie_refresh_requires_x_requested_with_and_rotates():
    client = get_client()
    register_user(client, EMAIL, PASSWORD)
    client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    old_cookie = client.cookies.get(settings.refresh_cookie_name)

    assert client.post("/auth/refresh").status_code == 403

    refreshed = client.post("/auth/refresh", headers=XRW)
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]
    new_cookie = client.cookies.get(settings.refresh_cookie_name)
    assert new_cookie and new_cookie != old_cookie


def test_refresh_token_reuse_revokes_the_whole_family():
    client = get_client()
    register_user(client, EMAIL, PASSWORD)
    first = _login_body(client)["refresh_token"]

    second = client.post("/auth/refresh", json={"refresh_token": first}).json()["refresh_token"]
    # Replaying the already-rotated token looks like theft...
    assert client.post("/auth/refresh", json={"refresh_token": first}).status_code == 401
    # ...so the legitimate newer token is revoked too.
    assert client.post("/auth/refresh", json={"refresh_token": second}).status_code == 401


def test_logout_revokes_refresh_token():
    client = get_client()
    register_user(client, EMAIL, PASSWORD)
    refresh = _login_body(client)["refresh_token"]
    assert client.post("/auth/logout", json={"refresh_token": refresh}).status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": refresh}).status_code == 401


def test_logout_all_invalidates_existing_access_tokens():
    client = get_client()
    headers = auth_headers(client, EMAIL, PASSWORD)
    assert client.get("/auth/me", headers=headers).status_code == 200
    assert client.post("/auth/logout-all", headers=headers).status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_lockout_after_repeated_failures():
    client = get_client()
    register_user(client, EMAIL, PASSWORD)
    for _ in range(5):
        response = client.post("/auth/login", json={"email": EMAIL, "password": "wrong-password"})
        assert response.status_code == 401
    locked = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert locked.status_code == 401
    assert "Too many failed" in locked.json()["detail"]


def test_unknown_email_gets_generic_error():
    client = get_client()
    response = client.post("/auth/login", json={"email": "nobody@example.com", "password": "x"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_unverified_user_cannot_add_sending_credentials():
    client = get_client()
    headers = auth_headers(client, EMAIL, PASSWORD, verify=False)
    me = client.get("/auth/me", headers=headers).json()
    assert me["email_verified_at"] is None
    response = client.post(
        "/provider-settings",
        headers=headers,
        json={"provider_type": "search", "provider_name": "bing", "config": {"api_key": "k"}},
    )
    assert response.status_code == 403

    token = latest_email_token(EMAIL, "verify")
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 200
    # Tokens are single use.
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 400


def test_password_reset_flow_invalidates_old_sessions():
    client = get_client()
    headers = auth_headers(client, EMAIL, PASSWORD)
    refresh = _login_body(client)["refresh_token"]

    response = client.post("/auth/forgot-password", json={"email": EMAIL})
    assert response.status_code == 202
    token = latest_email_token(EMAIL, "reset")

    reset = client.post("/auth/reset-password", json={"token": token, "password": "new-pass-777"})
    assert reset.status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": refresh}).status_code == 401
    assert (
        client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 401
    )
    assert login(client, EMAIL, "new-pass-777")


def test_forgot_password_does_not_reveal_unknown_accounts():
    client = get_client()
    response = client.post("/auth/forgot-password", json={"email": "ghost@example.com"})
    assert response.status_code == 202


def test_login_is_rate_limited_per_ip():
    client = get_client()
    register_user(client, EMAIL, PASSWORD)
    statuses = [
        client.post("/auth/login", json={"email": f"x{i}@example.com", "password": "x"}).status_code
        for i in range(11)
    ]
    assert statuses[-1] == 429


def test_refresh_token_cannot_be_used_as_access_token():
    client = get_client()
    register_user(client, EMAIL, PASSWORD)
    refresh = _login_body(client)["refresh_token"]
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {refresh}"})
    assert response.status_code == 401


def test_expired_access_token_is_rejected():
    client = get_client()
    register_user(client, EMAIL, PASSWORD)
    user_id = client.get("/auth/me", headers=login(client, EMAIL, PASSWORD)).json()["id"]
    expired = create_access_token(user_id, expires_delta=timedelta(seconds=-5))
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_session_hint_cookie_follows_the_refresh_cookie():
    client = get_client()
    register_user(client, EMAIL, PASSWORD)
    client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert client.cookies.get("lg_session") == "1"
    client.post("/auth/logout")
    assert client.cookies.get("lg_session") is None
