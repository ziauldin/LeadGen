"""OpenID Connect (authorization code flow with PKCE) for Google, Microsoft and workspace IdPs."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import jwt

from app.services.sso import http
from app.services.sso.http import SsoError

DISCOVERY_TTL = 3600
_discovery_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_jwks_cache: dict[str, tuple[float, dict[str, Any]]] = {}
ALLOWED_ALGORITHMS = ["RS256", "RS384", "RS512", "ES256", "ES384", "PS256"]


@dataclass(frozen=True)
class OidcClient:
    issuer: str
    client_id: str
    client_secret: str
    scopes: str = "openid email profile"
    # Microsoft's multi-tenant endpoint issues tokens whose issuer contains the tenant id.
    multi_tenant_issuer: bool = False


@dataclass(frozen=True)
class IdTokenClaims:
    subject: str
    email: str
    email_verified: bool
    name: str | None
    issuer: str
    raw: dict[str, Any]


def clear_caches() -> None:
    _discovery_cache.clear()
    _jwks_cache.clear()


def discover(issuer: str) -> dict[str, Any]:
    cached = _discovery_cache.get(issuer)
    if cached and cached[0] > time.time():
        return cached[1]
    document = http.transport.get_json(issuer.rstrip("/") + "/.well-known/openid-configuration")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not isinstance(document.get(key), str):
            raise SsoError("The identity provider's configuration is incomplete")
    _discovery_cache[issuer] = (time.time() + DISCOVERY_TTL, document)
    return document


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    return verifier, challenge


def authorization_url(
    client: OidcClient,
    *,
    redirect_uri: str,
    state: str,
    nonce: str,
    code_challenge: str,
    login_hint: str | None = None,
) -> str:
    document = discover(client.issuer)
    params = {
        "response_type": "code",
        "client_id": client.client_id,
        "redirect_uri": redirect_uri,
        "scope": client.scopes,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    if login_hint:
        params["login_hint"] = login_hint
    return f"{document['authorization_endpoint']}?{urlencode(params)}"


def _signing_key(jwks_uri: str, kid: str | None) -> jwt.PyJWK:
    for attempt in range(2):
        cached = _jwks_cache.get(jwks_uri)
        if not cached or cached[0] <= time.time() or attempt == 1:
            cached = (time.time() + DISCOVERY_TTL, http.transport.get_json(jwks_uri))
            _jwks_cache[jwks_uri] = cached
        for key in cached[1].get("keys", []):
            if kid is None or key.get("kid") == kid:
                return jwt.PyJWK(key)
    raise SsoError("The identity provider's signing key wasn't found")


def exchange_code(
    client: OidcClient,
    *,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    nonce: str,
) -> IdTokenClaims:
    document = discover(client.issuer)
    tokens = http.transport.post_form(
        document["token_endpoint"],
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client.client_id,
            "client_secret": client.client_secret,
            "code_verifier": code_verifier,
        },
    )
    id_token = tokens.get("id_token")
    if not isinstance(id_token, str):
        raise SsoError("The identity provider didn't return an ID token")
    return validate_id_token(client, id_token, nonce=nonce, document=document)


def validate_id_token(
    client: OidcClient,
    id_token: str,
    *,
    nonce: str,
    document: dict[str, Any] | None = None,
) -> IdTokenClaims:
    document = document or discover(client.issuer)
    try:
        header = jwt.get_unverified_header(id_token)
        if header.get("alg") not in ALLOWED_ALGORITHMS:
            raise SsoError("The identity provider used an unsupported signature")
        key = _signing_key(document["jwks_uri"], header.get("kid"))
        claims = jwt.decode(
            id_token,
            key.key,
            algorithms=ALLOWED_ALGORITHMS,
            audience=client.client_id,
            options={"require": ["iss", "sub", "aud", "exp", "iat"], "verify_iss": False},
            leeway=60,
        )
    except jwt.PyJWTError as exc:
        raise SsoError("The sign-in token from the identity provider wasn't valid") from exc

    issuer = str(claims.get("iss", ""))
    expected = str(document.get("issuer") or client.issuer)
    if client.multi_tenant_issuer:
        tenant = str(claims.get("tid", ""))
        ok = bool(tenant) and issuer == expected.replace("{tenantid}", tenant)
    else:
        ok = issuer.rstrip("/") == expected.rstrip("/")
    if not ok:
        raise SsoError("The sign-in token came from an unexpected issuer")
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise SsoError("The sign-in response didn't match this browser. Please try again.")

    email = str(claims.get("email") or claims.get("preferred_username") or "").strip().lower()
    if "@" not in email:
        raise SsoError("The identity provider didn't share an email address")
    return IdTokenClaims(
        subject=str(claims["sub"]),
        email=email,
        email_verified=claims.get("email_verified") in (True, "true"),
        name=claims.get("name"),
        issuer=issuer,
        raw=claims,
    )
