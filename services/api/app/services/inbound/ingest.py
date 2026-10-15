"""Store verified webhooks once, then process them (idempotently) in their workspace."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.tenancy import system_session, workspace_scope
from app.models.inbound import WebhookEvent
from app.services.inbound import normalize
from app.services.inbound.processor import process_delivery_event, process_inbound_email

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5


def store_event(
    db: Session,
    *,
    workspace_id: int,
    credential_id: int | None,
    provider: str,
    kind: str,
    event_id: str,
    event_type: str | None,
    payload: dict[str, Any],
) -> WebhookEvent | None:
    """Insert the event; returns None if we already have it (provider retry / replay)."""
    event = WebhookEvent(
        workspace_id=workspace_id,
        credential_id=credential_id,
        provider=provider,
        kind=kind,
        event_id=event_id[:255],
        event_type=(event_type or "")[:100] or None,
        payload=payload,
    )
    try:
        with db.begin_nested():
            db.add(event)
            db.flush()
    except IntegrityError:
        return None
    db.commit()
    return event


def _normalized(event: WebhookEvent) -> list[normalize.DeliveryEvent | normalize.InboundEmail]:
    payload = event.payload
    if event.provider == "resend":
        item = normalize.resend(payload, event.event_id)
        return [item] if item else []
    if event.provider == "sendgrid" and event.kind == "events":
        item = normalize.sendgrid_event(payload)
        return [item] if item else []
    if event.provider == "sendgrid" and event.kind == "inbound":
        return [normalize.sendgrid_inbound(payload)]
    if event.provider == "mailgun" and event.kind == "events":
        item = normalize.mailgun_event(payload)
        return [item] if item else []
    if event.provider == "mailgun" and event.kind == "inbound":
        return [normalize.mailgun_inbound(payload)]
    return []


def process_webhook_event(db: Session, event_id: int) -> str:
    with system_session(db):
        event = db.get(WebhookEvent, event_id)
        if event is None or event.status == "processed":
            return "skipped"
        workspace_id = event.workspace_id
    event.attempts += 1
    try:
        with workspace_scope(db, workspace_id):
            for item in _normalized(event):
                if isinstance(item, normalize.DeliveryEvent):
                    process_delivery_event(db, workspace_id, item)
                else:
                    process_inbound_email(db, workspace_id, item)
        event.status = "processed"
        event.processed_at = datetime.now(UTC)
        event.error = None
        db.commit()
        return "processed"
    except Exception as exc:
        db.rollback()
        logger.exception("Webhook event %s failed", event_id)
        with system_session(db):
            event = db.get(WebhookEvent, event_id)
            if event is not None:
                event.attempts = max(event.attempts, 1)
                event.status = "failed" if event.attempts >= MAX_ATTEMPTS else "retry"
                event.error = f"{exc.__class__.__name__}: {str(exc)[:500]}"
                db.commit()
        return "failed"


def retry_failed_events(db: Session, *, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    with system_session(db):
        ids = list(
            db.scalars(
                select(WebhookEvent.id)
                .where(
                    WebhookEvent.status.in_(["retry", "pending"]),
                    WebhookEvent.received_at >= now - timedelta(days=1),
                    WebhookEvent.received_at <= now - timedelta(minutes=2),
                )
                .limit(200),
            ).all(),
        )
    for event_id in ids:
        process_webhook_event(db, event_id)
    return len(ids)
