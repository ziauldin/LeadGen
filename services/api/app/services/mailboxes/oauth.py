"""Connect Gmail and Microsoft 365 mailboxes with OAuth (authorization code + PKCE).

The OAuth state is a short-lived signed token that carries the workspace, the user and the
PKCE verifier (encrypted), so no server-side state table is needed. Refresh tokens are stored
encrypted in the provider credential's config and access tokens are refreshed on demand.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

from app.core.config import settings
from app.core.errors import ValidationFailedError
from app.core.security import decrypt_secret_payload, encrypt_secret_payload


class MailboxAuthError(Exception):
    """The mailbox needs to be reconnected (revoked, expired or consent removed)."""


@dataclass(frozen=True)
class Provider:
    name: str  # matches ProviderName
    label: str
    authorize_url: str
    token_url: str
    scopes: tuple[str, ...]
    client_id_setting: str
    client_secret_setting: str
    extra_params: tuple[tuple[str, str], ...] = ()

    @property
    def client_id(self) -> str:
        return str(getattr(settings, self.client_id_setting))

    @property
    def client_secret(self) -> str:
        return str(getattr(settings, self.client_secret_setting))

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


PROVIDERS: dict[str, Provider] = {
    "gmail": Provider(
        name="gmail",
        label="Gmail / Google Workspace",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",  # noqa: S106 - URL, not a secret
        scopes=(
            "openid",
            "email",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.readonly",
        ),
        client_id_setting="google_oauth_client_id",
        client_secret_setting="google_oauth_client_secret",  # noqa: S106 - a settings name
        extra_params=(
            ("access_type", "offline"),
            ("prompt", "consent"),
            ("include_granted_scopes", "true"),
        ),
    ),
    "outlook": Provider(
        name="outlook",
        label="Microsoft 365 / Outlook",
        authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",  # noqa: S106
        scopes=("openid", "email", "offline_access", "Mail.Send", "Mail.Read", "User.Read"),
        client_id_setting="microsoft_oauth_client_id",
        client_secret_setting="microsoft_oauth_client_secret",  # noqa: S106 - a settings name
        extra_params=(("prompt", "select_account"),),
    ),
}

STATE_TYPE = "mailbox_oauth"
STATE_TTL = timedelta(minutes=10)


def provider(name: str) -> Provider:
    spec = PROVIDERS.get(name)
    if spec is None:
        raise ValidationFailedError("Unknown mailbox provider")
    if not spec.configured:
        raise ValidationFailedError(f"{spec.label} isn't set up on this server yet")
    return spec


def redirect_uri(name: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/api/mailboxes/oauth/{name}/callback"


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    return verifier, challenge


def authorization_url(name: str, *, workspace_id: int, user_id: int) -> str:
    spec = provider(name)
    verifier, challenge = _pkce()
    now = datetime.now(UTC)
    state = jwt.encode(
        {
            "typ": STATE_TYPE,
            "prv": name,
            "wsp": workspace_id,
            "sub": str(user_id),
            "pkv": encrypt_secret_payload(verifier),
            "nonce": secrets.token_hex(8),
            "iat": now,
            "exp": now + STATE_TTL,
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    params = {
        "client_id": spec.client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri(name),
        "scope": " ".join(spec.scopes),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        **dict(spec.extra_params),
    }
    return f"{spec.authorize_url}?{urlencode(params)}"


@dataclass
class OAuthState:
    provider: str
    workspace_id: int
    user_id: int
    verifier: str


def read_state(token: str, name: str) -> OAuthState:
    try:
        claims = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise ValidationFailedError("This connection link has expired. Please try again.") from exc
    if claims.get("typ") != STATE_TYPE or claims.get("prv") != name:
        raise ValidationFailedError("This connection link is invalid. Please try again.")
    return OAuthState(
        provider=name,
        workspace_id=int(claims["wsp"]),
        user_id=int(claims["sub"]),
        verifier=decrypt_secret_payload(claims["pkv"]),
    )


def http_client() -> httpx.Client:
    """Overridden in tests with a mock transport."""
    return httpx.Client(timeout=20.0)


def _token_request(spec: Provider, data: dict[str, str]) -> dict[str, Any]:
    with http_client() as client:
        response = client.post(
            spec.token_url,
            data={"client_id": spec.client_id, "client_secret": spec.client_secret, **data},
            headers={"Accept": "application/json"},
        )
    body = response.json() if response.content else {}
    if response.status_code >= 400:
        error = body.get("error", "")
        if error in ("invalid_grant", "unauthorized_client", "interaction_required"):
            raise MailboxAuthError(body.get("error_description") or error)
        raise ValidationFailedError(
            f"The provider refused the request ({error or response.status_code})"
        )
    return body


def exchange_code(name: str, code: str, verifier: str) -> dict[str, Any]:
    spec = provider(name)
    return _token_request(
        spec,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri(name),
            "code_verifier": verifier,
        },
    )


def refresh(name: str, refresh_token: str) -> dict[str, Any]:
    spec = provider(name)
    return _token_request(spec, {"grant_type": "refresh_token", "refresh_token": refresh_token})


def expires_at(token_response: dict[str, Any]) -> str:
    seconds = int(token_response.get("expires_in", 3600))
    return (datetime.now(UTC) + timedelta(seconds=max(60, seconds - 60))).isoformat()
