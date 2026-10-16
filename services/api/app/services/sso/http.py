"""HTTP for identity providers. Admin-supplied issuer URLs go through the SSRF-safe helpers.

Tests replace ``client`` on the module-level ``transport`` with a stub.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

import httpx

from app.core.http import FetchError, UnsafeURLError, safe_get, safe_post_form

MAX_BYTES = 1_000_000
TIMEOUT = 10.0


class SsoError(Exception):
    """Sign-in with an identity provider failed. The message is safe to show to users."""


class Transport(Protocol):
    def get_json(self, url: str) -> dict[str, Any]: ...
    def post_form(self, url: str, data: dict[str, str]) -> dict[str, Any]: ...


class SafeTransport:
    def __init__(self) -> None:
        self.client = httpx.Client()

    def _json(self, text: str, status: int) -> dict[str, Any]:
        if status >= 400:
            raise SsoError(f"The identity provider returned an error (HTTP {status})")
        try:
            value = json.loads(text)
        except ValueError as exc:
            raise SsoError("The identity provider sent an unreadable response") from exc
        if not isinstance(value, dict):
            raise SsoError("The identity provider sent an unexpected response")
        return value

    def get_json(self, url: str) -> dict[str, Any]:
        try:
            result = safe_get(self.client, url, timeout=TIMEOUT, max_bytes=MAX_BYTES)
        except (FetchError, UnsafeURLError) as exc:
            raise SsoError(f"Couldn't reach the identity provider: {exc}") from exc
        return self._json(result.text, result.status_code)

    def post_form(self, url: str, data: dict[str, str]) -> dict[str, Any]:
        try:
            result = safe_post_form(
                self.client,
                url,
                data,
                timeout=TIMEOUT,
                max_bytes=MAX_BYTES,
                headers={"Accept": "application/json"},
            )
        except (FetchError, UnsafeURLError) as exc:
            raise SsoError(f"Couldn't reach the identity provider: {exc}") from exc
        return self._json(result.text, result.status_code)


transport: Transport = SafeTransport()
