"""Outbound webhooks: signed event notifications with retries and a delivery log."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import event, select
from sqlalchemy.orm import Session, SessionTransaction

from app.core.config import settings
from app.core.errors import ValidationFailedError
from app.core.http import FetchError, UnsafeURLError, safe_post_bytes
from app.core.security import decrypt_secret_payload, encrypt_secret_payload
from app.models.developer import WebhookDelivery, WebhookEndpoint

logger = logging.getLogger(__name__)

EVENTS: dict[str, str] = {
    "lead.created": "A lead was added (by hand, import, search or the API)",
    "email.sent": "An email was accepted by the sending provider",
    "email.bounced": "An email bounced or was marked as spam",
    "reply.received": "Someone replied to one of your emails",
    "enrollment.completed": "A lead finished a campaign sequence",
}
# Seconds to wait before attempt 2, 3, ... (8 attempts over about two days).
RETRY_SCHEDULE = [60, 300, 1800, 7200, 21600, 43200, 86400]
DISABLE_AFTER_FAILURES = 50
PENDING_KEY = "outbound_webhook_ids"


def new_secret() -> str:
    return "whsec_" + secrets.token_urlsafe(32)


def endpoint_secret(endpoint: WebhookEndpoint) -> str:
    return decrypt_secret_payload(endpoint.secret_encrypted)


def set_secret(endpoint: WebhookEndpoint, secret: str) -> None:
    endpoint.secret_encrypted = encrypt_secret_payload(secret)


def validate_endpoint_url(url: str) -> str:
    """Basic checks when saving; every delivery is also checked by the SSRF-safe client."""
    parsed = urlparse(url.strip())
    local = settings.environment in ("development", "test")
    if parsed.scheme not in ("https", "http") or (parsed.scheme == "http" and not local):
        raise ValidationFailedError("Webhook URLs must use https")
    host = (parsed.hostname or "").lower()
    if not host or host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        raise ValidationFailedError("Webhook URLs must point to a public server")
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ValidationFailedError("Webhook URLs must point to a public server")
    except ValueError:
        pass  # a hostname, resolved and checked at delivery time
    return url.strip()


def validate_events(events: list[str]) -> list[str]:
    unknown = sorted(set(events) - EVENTS.keys())
    if unknown:
        raise ValidationFailedError(f"Unknown events: {', '.join(unknown)}")
    if not events:
        raise ValidationFailedError("Choose at least one event")
    return sorted(set(events))


def sign(secret: str, timestamp: int, body: bytes) -> str:
    digest = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def emit_event(db: Session, workspace_id: int, event_type: str, data: dict[str, Any]) -> list[int]:
    """Queue ``event_type`` for every active endpoint subscribed to it.

    Deliveries are written in the caller's transaction and sent once it commits.
    """
    if event_type not in EVENTS and event_type != "ping":
        raise ValueError(f"Unknown webhook event {event_type}")
    endpoints = [
        endpoint
        for endpoint in db.scalars(
            select(WebhookEndpoint).where(
                WebhookEndpoint.workspace_id == workspace_id, WebhookEndpoint.is_active.is_(True)
            )
        ).all()
        if event_type in (endpoint.events or [])
    ]
    if not endpoints:
        return []
    return _queue(db, workspace_id, endpoints, event_type, data)


def _queue(
    db: Session,
    workspace_id: int,
    endpoints: list[WebhookEndpoint],
    event_type: str,
    data: dict[str, Any],
    event_id: str | None = None,
) -> list[int]:
    event_id = event_id or "evt_" + secrets.token_hex(12)
    payload = {
        "id": event_id,
        "type": event_type,
        "created_at": datetime.now(UTC).isoformat(),
        "workspace_id": workspace_id,
        "data": data,
    }
    deliveries = [
        WebhookDelivery(
            workspace_id=workspace_id,
            endpoint_id=endpoint.id,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            status="pending",
            next_attempt_at=datetime.now(UTC),
        )
        for endpoint in endpoints
    ]
    db.add_all(deliveries)
    db.flush()
    ids = [delivery.id for delivery in deliveries]
    db.info.setdefault(PENDING_KEY, []).extend(ids)
    return ids


def send_test_event(db: Session, endpoint: WebhookEndpoint) -> int:
    return _queue(
        db, endpoint.workspace_id, [endpoint], "ping", {"message": "Webhook test from LeadsGen"}
    )[0]


def replay(db: Session, delivery: WebhookDelivery) -> int:
    """Send the same event again (same event id, so receivers can de-duplicate)."""
    endpoint = db.get(WebhookEndpoint, delivery.endpoint_id)
    assert endpoint is not None  # noqa: S101 - FK
    return _queue(
        db,
        delivery.workspace_id,
        [endpoint],
        delivery.event_type,
        delivery.payload["data"],
        delivery.event_id,
    )[0]


@event.listens_for(Session, "after_transaction_end")
def _send_after_commit(session: Session, transaction: SessionTransaction) -> None:
    # after_commit also fires when a SAVEPOINT is released; only send once the outermost
    # transaction has really committed (a rollback clears the queue first, see below).
    if transaction.parent is not None or transaction.nested:
        return
    ids = session.info.pop(PENDING_KEY, None)
    if not ids:
        return
    from app.workers.outbound_webhook_jobs import deliver_outbound_webhook

    for delivery_id in ids:
        try:
            deliver_outbound_webhook.delay(delivery_id)
        except Exception:  # the retry sweep picks it up
            logger.exception("Could not enqueue webhook delivery %s", delivery_id)


@event.listens_for(Session, "after_rollback")
def _forget_after_rollback(session: Session) -> None:
    session.info.pop(PENDING_KEY, None)


def _http_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": "LeadsGen-Webhooks/1.0"})


def attempt_delivery(db: Session, delivery_id: int) -> str:
    """Try to deliver once. Schedules the next attempt or gives up. Returns the new status."""
    delivery = db.get(WebhookDelivery, delivery_id)
    if delivery is None or delivery.status != "pending":
        return delivery.status if delivery else "missing"
    endpoint = db.get(WebhookEndpoint, delivery.endpoint_id)
    if endpoint is None or not endpoint.is_active:
        delivery.status = "failed"
        delivery.error = "Endpoint disabled or deleted"
        delivery.next_attempt_at = None
        db.commit()
        return delivery.status

    body = json.dumps(delivery.payload, separators=(",", ":"), default=str).encode()
    timestamp = int(time.time())
    headers = {
        "Content-Type": "application/json",
        "LeadsGen-Event": delivery.event_type,
        "LeadsGen-Delivery": str(delivery.id),
        "LeadsGen-Event-Id": delivery.event_id,
        "LeadsGen-Signature": sign(endpoint_secret(endpoint), timestamp, body),
    }
    delivery.attempts += 1
    ok = False
    try:
        with _http_client() as client:
            result = safe_post_bytes(
                client,
                endpoint.url,
                body,
                headers=headers,
                timeout=settings.outbound_webhook_timeout_seconds,
                max_bytes=64_000,
            )
        delivery.response_status = result.status_code
        delivery.response_body = result.text[:2000]
        ok = 200 <= result.status_code < 300
        delivery.error = None if ok else f"Endpoint answered {result.status_code}"
    except (FetchError, UnsafeURLError) as exc:
        delivery.response_status = None
        delivery.error = str(exc)[:500]

    if ok:
        delivery.status = "succeeded"
        delivery.delivered_at = datetime.now(UTC)
        delivery.next_attempt_at = None
        endpoint.consecutive_failures = 0
    else:
        endpoint.consecutive_failures += 1
        if delivery.attempts > len(RETRY_SCHEDULE):
            delivery.status = "failed"
            delivery.next_attempt_at = None
        else:
            delivery.next_attempt_at = datetime.now(UTC) + timedelta(
                seconds=RETRY_SCHEDULE[delivery.attempts - 1]
            )
        if endpoint.consecutive_failures >= DISABLE_AFTER_FAILURES:
            endpoint.is_active = False
            endpoint.disabled_reason = (
                f"Disabled after {DISABLE_AFTER_FAILURES} failed deliveries in a row"
            )
    db.commit()
    return delivery.status


def due_deliveries(db: Session, *, limit: int = 200) -> list[int]:
    now = datetime.now(UTC)
    return list(
        db.scalars(
            select(WebhookDelivery.id)
            .where(WebhookDelivery.status == "pending", WebhookDelivery.next_attempt_at <= now)
            .order_by(WebhookDelivery.next_attempt_at)
            .limit(limit)
        ).all()
    )
