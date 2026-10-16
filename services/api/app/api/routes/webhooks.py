"""Provider webhooks: delivery events and inbound replies.

URL shape: ``/webhooks/{provider}/{token}[/events|/inbound]``. The random ``token`` belongs to
one sending credential, which tells us the workspace and the signing secret to check.
Requests are verified, stored once, and processed asynchronously; we answer 200 quickly so the
provider doesn't retry needlessly.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import metrics
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.enums import ProviderName, ProviderType
from app.models.provider_credential import ProviderCredential
from app.services.inbound.ingest import store_event
from app.services.inbound.signatures import (
    SignatureError,
    verify_mailgun,
    verify_sendgrid,
    verify_svix,
)
from app.services.provider_credentials.service import _as_str, decrypt_provider_config

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 10_000_000


def _credential(db: Session, provider: ProviderName, token: str) -> ProviderCredential:
    if not settings.feature_inbound_webhooks:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    credential = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.webhook_token == token,
            ProviderCredential.provider_type == ProviderType.EMAIL,
        ),
    )
    if credential is None or _as_str(credential.provider_name) != provider.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return credential


async def _body(request: Request) -> bytes:
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Payload too large"
        )
    return body


def _reject(exc: SignatureError) -> HTTPException:
    logger.warning("Webhook signature rejected: %s", exc)
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")


def _enqueue(event_ids: list[int]) -> None:
    from app.workers.inbound_jobs import process_webhook_task

    for event_id in event_ids:
        try:
            process_webhook_task.delay(event_id)
        except Exception:
            logger.warning("Could not queue webhook event %s; it will be retried", event_id)


def _store(
    db: Session,
    credential: ProviderCredential,
    provider: str,
    kind: str,
    items: Sequence[tuple[str, str | None, dict[str, Any]]],
) -> dict[str, int]:
    stored: list[int] = []
    for event_id, event_type, payload in items:
        event = store_event(
            db,
            workspace_id=credential.workspace_id,
            credential_id=credential.id,
            provider=provider,
            kind=kind,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
        )
        if event is not None:
            stored.append(event.id)
    _enqueue(stored)
    metrics.WEBHOOKS_RECEIVED.labels(provider).inc(len(stored))
    return {"received": len(items), "stored": len(stored)}


@router.post("/resend/{token}")
@limiter.limit("600/minute")
async def resend_webhook(request: Request, token: str, db: Session = Depends(get_db)) -> dict:
    credential = _credential(db, ProviderName.RESEND, token)
    body = await _body(request)
    secret = str(decrypt_provider_config(credential).get("webhook_secret") or "")
    try:
        verify_svix(
            secret,
            msg_id=request.headers.get("svix-id"),
            timestamp=request.headers.get("svix-timestamp"),
            signature_header=request.headers.get("svix-signature"),
            body=body,
        )
    except SignatureError as exc:
        raise _reject(exc) from None
    payload = json.loads(body or b"{}")
    event_type = str(payload.get("type", ""))
    kind = "inbound" if event_type == "email.received" else "events"
    return _store(
        db,
        credential,
        "resend",
        kind,
        [(request.headers.get("svix-id") or "", event_type, payload)],
    )


@router.post("/sendgrid/{token}/events")
@limiter.limit("600/minute")
async def sendgrid_events(request: Request, token: str, db: Session = Depends(get_db)) -> dict:
    credential = _credential(db, ProviderName.SENDGRID, token)
    body = await _body(request)
    public_key = str(decrypt_provider_config(credential).get("event_public_key") or "")
    try:
        verify_sendgrid(
            public_key,
            signature=request.headers.get("X-Twilio-Email-Event-Webhook-Signature"),
            timestamp=request.headers.get("X-Twilio-Email-Event-Webhook-Timestamp"),
            body=body,
        )
    except SignatureError as exc:
        raise _reject(exc) from None
    events = json.loads(body or b"[]")
    items = [
        (
            str(item.get("sg_event_id") or f"{item.get('sg_message_id')}:{item.get('event')}"),
            str(item.get("event")),
            item,
        )
        for item in events
        if isinstance(item, dict)
    ]
    return _store(db, credential, "sendgrid", "events", items)


@router.post("/sendgrid/{token}/inbound")
@limiter.limit("300/minute")
async def sendgrid_inbound(request: Request, token: str, db: Session = Depends(get_db)) -> dict:
    # SendGrid Inbound Parse cannot sign requests: the secret token in the URL authenticates it.
    credential = _credential(db, ProviderName.SENDGRID, token)
    await _body(request)
    form = await request.form()
    payload = {key: str(value) for key, value in form.items() if isinstance(value, str)}
    digest = hashlib.sha256(
        (payload.get("headers", "") + payload.get("text", "")).encode(),
    ).hexdigest()
    event_id = f"inbound:{digest}"
    message_id = next(
        (
            line.partition(":")[2].strip()
            for line in payload.get("headers", "").splitlines()
            if line.lower().startswith("message-id:")
        ),
        None,
    )
    return _store(
        db,
        credential,
        "sendgrid",
        "inbound",
        [(message_id or event_id, "inbound", payload)],
    )


def _mailgun_signature(source: dict[str, Any]) -> dict[str, str]:
    signature = source.get("signature")
    if isinstance(signature, dict):
        return {k: str(v) for k, v in signature.items()}
    return {
        "timestamp": str(source.get("timestamp") or ""),
        "token": str(source.get("token") or ""),
        "signature": str(signature or ""),
    }


@router.post("/mailgun/{token}/events")
@limiter.limit("600/minute")
async def mailgun_events(request: Request, token: str, db: Session = Depends(get_db)) -> dict:
    credential = _credential(db, ProviderName.MAILGUN, token)
    body = await _body(request)
    payload = json.loads(body or b"{}")
    sig = _mailgun_signature(payload)
    key = str(decrypt_provider_config(credential).get("webhook_signing_key") or "")
    try:
        verify_mailgun(
            key, timestamp=sig["timestamp"], token=sig["token"], signature=sig["signature"]
        )
    except SignatureError as exc:
        raise _reject(exc) from None
    data = payload.get("event-data") or {}
    return _store(
        db,
        credential,
        "mailgun",
        "events",
        [(str(data.get("id") or sig["token"]), str(data.get("event")), payload)],
    )


@router.post("/mailgun/{token}/inbound")
@limiter.limit("300/minute")
async def mailgun_inbound(request: Request, token: str, db: Session = Depends(get_db)) -> dict:
    credential = _credential(db, ProviderName.MAILGUN, token)
    await _body(request)
    form = await request.form()
    payload = {key: str(value) for key, value in form.items() if isinstance(value, str)}
    sig = _mailgun_signature(payload)
    key = str(decrypt_provider_config(credential).get("webhook_signing_key") or "")
    try:
        verify_mailgun(
            key, timestamp=sig["timestamp"], token=sig["token"], signature=sig["signature"]
        )
    except SignatureError as exc:
        raise _reject(exc) from None
    return _store(
        db,
        credential,
        "mailgun",
        "inbound",
        [(payload.get("Message-Id") or sig["token"], "inbound", payload)],
    )
