"""Abuse protection: breached-password checks (Have I Been Pwned) and Cloudflare Turnstile."""

from __future__ import annotations

import hashlib
import logging

import httpx

from app.core.config import settings
from app.core.errors import ValidationFailedError

logger = logging.getLogger(__name__)

HIBP_RANGE_URL = "https://api.pwnedpasswords.com/range/"
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def breach_count(password: str, *, client: httpx.Client | None = None) -> int:
    """How often a password appears in known breaches, via k-anonymity.

    Only the first five characters of the SHA-1 hash leave the server. If the service can't
    be reached, the check is skipped (returns 0) rather than blocking sign-up.
    """
    digest = hashlib.sha1(password.encode(), usedforsecurity=False).hexdigest().upper()
    prefix, suffix = digest[:5], digest[5:]
    http = client or httpx.Client(timeout=3.0)
    try:
        response = http.get(HIBP_RANGE_URL + prefix, headers={"Add-Padding": "true"})
        response.raise_for_status()
    except httpx.HTTPError:
        logger.warning("Breached-password check unavailable; skipping")
        return 0
    finally:
        if client is None:
            http.close()
    for line in response.text.splitlines():
        candidate, _, count = line.partition(":")
        if candidate.strip() == suffix:
            return int(count.strip() or 0)
    return 0


def ensure_password_not_breached(password: str) -> None:
    if not settings.password_breach_check:
        return
    if breach_count(password) > 0:
        raise ValidationFailedError(
            "This password has appeared in a known data breach. Please choose a different one.",
        )


def captcha_enabled() -> bool:
    return bool(settings.turnstile_secret_key)


def verify_captcha(
    token: str | None, *, remote_ip: str | None = None, client: httpx.Client | None = None
) -> None:
    """Raise unless Turnstile accepts the token. Does nothing when no secret is configured."""
    if not captcha_enabled():
        return
    if not token:
        raise ValidationFailedError(
            "Please complete the security check", extra={"code": "captcha_required"}
        )
    http = client or httpx.Client(timeout=5.0)
    try:
        response = http.post(
            TURNSTILE_VERIFY_URL,
            data={
                "secret": settings.turnstile_secret_key,
                "response": token,
                **({"remoteip": remote_ip} if remote_ip else {}),
            },
        )
        ok = response.status_code == 200 and bool(response.json().get("success"))
    except (httpx.HTTPError, ValueError):
        ok = False
    finally:
        if client is None:
            http.close()
    if not ok:
        raise ValidationFailedError(
            "The security check failed. Please try again.", extra={"code": "captcha_required"}
        )
