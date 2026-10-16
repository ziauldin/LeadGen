"""A small Stripe REST client (no SDK): form-encoded requests and webhook signature checks."""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import httpx

from app.core.config import settings


class StripeError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class SignatureError(Exception):
    pass


def encode(params: dict[str, Any], prefix: str = "") -> list[tuple[str, str]]:
    """Stripe's nested form encoding: {"a": {"b": [1]}} -> [("a[b][0]", "1")]."""
    pairs: list[tuple[str, str]] = []
    for key, value in params.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if value is None:
            continue
        if isinstance(value, dict):
            pairs.extend(encode(value, name))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, dict):
                    pairs.extend(encode(item, f"{name}[{index}]"))
                else:
                    pairs.append((f"{name}[{index}]", _scalar(item)))
        else:
            pairs.append((name, _scalar(value)))
    return pairs


def _scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class StripeClient:
    def __init__(self, secret_key: str | None = None) -> None:
        self.secret_key = secret_key or settings.stripe_secret_key

    def request(
        self, method: str, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"{settings.stripe_api_base.rstrip('/')}/{path.lstrip('/')}"
        data = encode(params or {})
        headers = {"Authorization": f"Bearer {self.secret_key}", "Stripe-Version": "2024-06-20"}
        try:
            with httpx.Client(timeout=20.0) as client:
                if method == "GET":
                    response = client.get(url, params=tuple(data), headers=headers)
                else:
                    response = client.request(method, url, data=dict(data), headers=headers)
        except httpx.HTTPError as exc:
            raise StripeError(f"Could not reach Stripe ({exc.__class__.__name__})") from exc
        body = response.json() if response.content else {}
        if response.status_code >= 400:
            message = (body.get("error") or {}).get(
                "message"
            ) or f"Stripe error {response.status_code}"
            raise StripeError(message, response.status_code)
        return body

    def create_customer(self, *, email: str, name: str, workspace_id: int) -> dict[str, Any]:
        return self.request(
            "POST",
            "customers",
            {"email": email, "name": name, "metadata": {"workspace_id": workspace_id}},
        )

    def create_checkout_session(self, params: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "checkout/sessions", params)

    def create_portal_session(self, *, customer: str, return_url: str) -> dict[str, Any]:
        return self.request(
            "POST", "billing_portal/sessions", {"customer": customer, "return_url": return_url}
        )

    def retrieve_subscription(self, subscription_id: str) -> dict[str, Any]:
        return self.request("GET", f"subscriptions/{subscription_id}")

    def list_invoices(self, customer: str, limit: int = 12) -> dict[str, Any]:
        return self.request("GET", "invoices", {"customer": customer, "limit": limit})


def verify_signature(payload: bytes, header: str, secret: str, *, tolerance: int = 300) -> None:
    """Check a ``Stripe-Signature`` header (``t=...,v1=...``) against the endpoint secret."""
    if not secret:
        raise SignatureError("Stripe webhook secret is not configured")
    timestamp = None
    signatures: list[str] = []
    for part in (header or "").split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            signatures.append(value)
    if not timestamp or not signatures:
        raise SignatureError("Malformed Stripe-Signature header")
    try:
        age = abs(time.time() - int(timestamp))
    except ValueError as exc:
        raise SignatureError("Malformed timestamp") from exc
    if age > tolerance:
        raise SignatureError("Signature timestamp is too old")
    expected = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    if not any(hmac.compare_digest(expected, signature) for signature in signatures):
        raise SignatureError("Signature doesn't match")
