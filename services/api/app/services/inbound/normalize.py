"""Turn provider-specific payloads into two neutral shapes the processor understands."""

from __future__ import annotations

import email
import email.policy
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage as MimeMessage
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from typing import Any

DELIVERED = "delivered"
BOUNCE_HARD = "bounce_hard"
BOUNCE_SOFT = "bounce_soft"
COMPLAINT = "complaint"
UNSUBSCRIBE = "unsubscribe"


@dataclass
class DeliveryEvent:
    kind: str
    provider: str
    event_id: str
    recipient: str | None = None
    provider_message_id: str | None = None
    correlation_id: str | None = None  # our email_messages.id (tag / custom arg)
    reason: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class InboundEmail:
    from_email: str
    to: list[str]
    subject: str | None
    text: str
    message_id: str | None = None
    in_reply_to: str | None = None
    references: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    content_type: str | None = None
    received_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    failed_recipients: list[str] = field(default_factory=list)


_ID_RE = re.compile(r"<([^>]+)>")


def message_ids(value: str | None) -> list[str]:
    """Message-IDs from a header value, without angle brackets."""
    if not value:
        return []
    found = _ID_RE.findall(value)
    return found or [part.strip() for part in value.split() if part.strip()]


def _address(value: str | None) -> str:
    return parseaddr(value or "")[1].strip().lower()


def _addresses(value: str | list[str] | None) -> list[str]:
    if not value:
        return []
    values = value if isinstance(value, list) else [value]
    return [addr.lower() for _, addr in getaddresses(values) if addr]


def _ts(value: Any) -> datetime:
    if isinstance(value, int | float):
        return datetime.fromtimestamp(float(value), tz=UTC)
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(UTC)


def _text_from_html(html: str) -> str:
    text = re.sub(r"<(br|/p|/div)[^>]*>", "\n", html, flags=re.IGNORECASE)
    return re.sub(r"<[^>]+>", "", text)


# --- Raw RFC 822 (IMAP, SendGrid Inbound Parse "email" field) -------------------------------


def from_rfc822(raw: bytes | str) -> InboundEmail:
    parsed = (
        email.message_from_bytes(raw, policy=email.policy.default)
        if isinstance(raw, bytes)
        else email.message_from_string(raw, policy=email.policy.default)
    )
    assert isinstance(parsed, MimeMessage)  # noqa: S101 - default policy returns EmailMessage
    body = parsed.get_body(preferencelist=("plain", "html"))
    text = ""
    if body is not None:
        content = body.get_content()
        text = content if body.get_content_type() == "text/plain" else _text_from_html(content)
    failed = _addresses(parsed.get("X-Failed-Recipients"))
    if parsed.get_content_type() == "multipart/report":
        for part in parsed.walk():
            if part.get_content_type() == "message/delivery-status":
                payload = part.get_payload()
                blocks = payload if isinstance(payload, list) else [payload]
                for block in blocks:
                    recipient = (
                        str(block.get("Final-Recipient", "")) if hasattr(block, "get") else ""
                    )
                    if ";" in recipient:
                        failed.append(recipient.split(";", 1)[1].strip().lower())
            if part.get_content_type() in {"message/rfc822", "text/rfc822-headers"}:
                inner = part.get_payload()
                inner_msg = inner[0] if isinstance(inner, list) and inner else inner
                original = inner_msg.get("Message-ID") if hasattr(inner_msg, "get") else None
                if original:
                    parsed["X-Original-Message-ID"] = original
    received = parsed.get("Date")
    try:
        received_at = parsedate_to_datetime(received) if received else datetime.now(UTC)
    except (TypeError, ValueError):
        received_at = datetime.now(UTC)
    references = message_ids(parsed.get("References"))
    original_id = message_ids(parsed.get("X-Original-Message-ID"))
    return InboundEmail(
        from_email=_address(parsed.get("From")),
        to=_addresses(parsed.get_all("To", [])) + _addresses(parsed.get_all("Delivered-To", [])),
        subject=str(parsed.get("Subject") or "") or None,
        text=text,
        message_id=(message_ids(parsed.get("Message-ID")) or [None])[0],
        in_reply_to=(message_ids(parsed.get("In-Reply-To")) or original_id or [None])[0],
        references=references + original_id,
        headers={key: str(value) for key, value in parsed.items()},
        content_type=parsed.get_content_type(),
        received_at=received_at if received_at.tzinfo else received_at.replace(tzinfo=UTC),
        failed_recipients=sorted(set(failed)),
    )


# --- Resend -----------------------------------------------------------------------------------


def resend(payload: dict[str, Any], event_id: str) -> DeliveryEvent | InboundEmail | None:
    event_type = str(payload.get("type", ""))
    data = payload.get("data") or {}
    if event_type == "email.received":
        headers = {str(k): str(v) for k, v in (data.get("headers") or {}).items()}
        text = data.get("text") or _text_from_html(data.get("html") or "")
        return InboundEmail(
            from_email=_address(data.get("from")),
            to=_addresses(data.get("to")),
            subject=data.get("subject"),
            text=text,
            message_id=(
                message_ids(headers.get("Message-ID") or headers.get("message-id")) or [None]
            )[0],
            in_reply_to=(
                message_ids(headers.get("In-Reply-To") or headers.get("in-reply-to")) or [None]
            )[0],
            references=message_ids(headers.get("References") or headers.get("references")),
            headers=headers,
            received_at=_ts(payload.get("created_at") or data.get("created_at")),
        )
    tags = data.get("tags") or {}
    if isinstance(tags, list):
        tags = {t.get("name"): t.get("value") for t in tags if isinstance(t, dict)}
    kinds = {
        "email.delivered": DELIVERED,
        "email.complained": COMPLAINT,
    }
    kind = kinds.get(event_type)
    reason = None
    if event_type == "email.bounced":
        bounce = data.get("bounce") or {}
        reason = bounce.get("message") or bounce.get("subType")
        kind = BOUNCE_SOFT if str(bounce.get("type", "")).lower() == "transient" else BOUNCE_HARD
    if kind is None:
        return None
    recipients = _addresses(data.get("to"))
    return DeliveryEvent(
        kind=kind,
        provider="resend",
        event_id=event_id,
        recipient=recipients[0] if recipients else None,
        provider_message_id=data.get("email_id"),
        correlation_id=str(tags.get("lg_msg_id")) if tags.get("lg_msg_id") else None,
        reason=reason,
        occurred_at=_ts(payload.get("created_at")),
    )


# --- SendGrid ---------------------------------------------------------------------------------


def sendgrid_event(item: dict[str, Any]) -> DeliveryEvent | None:
    event = str(item.get("event", ""))
    kind = {
        "delivered": DELIVERED,
        "spamreport": COMPLAINT,
        "unsubscribe": UNSUBSCRIBE,
        "group_unsubscribe": UNSUBSCRIBE,
    }.get(event)
    if event in {"bounce", "dropped"}:
        kind = BOUNCE_SOFT if str(item.get("type")) == "blocked" else BOUNCE_HARD
    elif event == "deferred":
        kind = None
    if kind is None:
        return None
    sg_id = str(item.get("sg_message_id") or "")
    return DeliveryEvent(
        kind=kind,
        provider="sendgrid",
        event_id=str(item.get("sg_event_id") or f"{sg_id}:{event}:{item.get('timestamp')}"),
        recipient=str(item.get("email") or "").lower() or None,
        provider_message_id=sg_id.split(".", 1)[0] or None,
        correlation_id=str(item["lg_msg_id"]) if item.get("lg_msg_id") else None,
        reason=item.get("reason"),
        occurred_at=_ts(item.get("timestamp")),
    )


def sendgrid_inbound(form: dict[str, Any]) -> InboundEmail:
    if form.get("email"):
        return from_rfc822(str(form["email"]))  # "Send raw" option
    headers: dict[str, str] = {}
    for line in str(form.get("headers") or "").splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            key, _, value = line.partition(":")
            headers[key.strip()] = value.strip()
    return InboundEmail(
        from_email=_address(form.get("from")),
        to=_addresses(form.get("to")),
        subject=form.get("subject"),
        text=str(form.get("text") or _text_from_html(str(form.get("html") or ""))),
        message_id=(message_ids(headers.get("Message-ID")) or [None])[0],
        in_reply_to=(message_ids(headers.get("In-Reply-To")) or [None])[0],
        references=message_ids(headers.get("References")),
        headers=headers,
    )


# --- Mailgun ----------------------------------------------------------------------------------


def mailgun_event(payload: dict[str, Any]) -> DeliveryEvent | None:
    data = payload.get("event-data") or {}
    event = str(data.get("event", ""))
    kind = {
        "delivered": DELIVERED,
        "complained": COMPLAINT,
        "unsubscribed": UNSUBSCRIBE,
    }.get(event)
    if event == "failed":
        kind = BOUNCE_HARD if data.get("severity") == "permanent" else BOUNCE_SOFT
    if kind is None:
        return None
    message = data.get("message") or {}
    headers = message.get("headers") or {}
    variables = data.get("user-variables") or {}
    status = data.get("delivery-status") or {}
    return DeliveryEvent(
        kind=kind,
        provider="mailgun",
        event_id=str(data.get("id") or payload.get("signature", {}).get("token")),
        recipient=str(data.get("recipient") or "").lower() or None,
        provider_message_id=str(headers.get("message-id") or "").strip("<>") or None,
        correlation_id=str(variables["lg_msg_id"]) if variables.get("lg_msg_id") else None,
        reason=status.get("description") or status.get("message"),
        occurred_at=_ts(data.get("timestamp")),
    )


def mailgun_inbound(form: dict[str, Any]) -> InboundEmail:
    return InboundEmail(
        from_email=_address(form.get("sender") or form.get("from")),
        to=_addresses(form.get("recipient") or form.get("To")),
        subject=form.get("subject"),
        text=str(form.get("body-plain") or form.get("stripped-text") or ""),
        message_id=(message_ids(form.get("Message-Id")) or [None])[0],
        in_reply_to=(message_ids(form.get("In-Reply-To")) or [None])[0],
        references=message_ids(form.get("References")),
        headers={k: str(v) for k, v in form.items() if k[:1].isupper()},
    )
