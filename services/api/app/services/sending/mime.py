"""Turn an approved email message into what we hand to the provider."""

from __future__ import annotations

import html
import re
import uuid

from app.core.config import settings
from app.models.email_message import EmailMessage
from app.models.workspace import WorkspaceSettings
from app.services.email_generation.personalisation import unsubscribe_url
from app.services.sending.base import OutboundEmail

_URL_RE = re.compile(r"(https?://[^\s<>\"']+)")


def make_message_id(from_email: str) -> str:
    domain = from_email.rsplit("@", 1)[-1] if "@" in from_email else "leadsgen.local"
    return f"lg.{uuid.uuid4().hex}@{domain}"


def _footer(message: EmailMessage, workspace_settings: WorkspaceSettings | None) -> str:
    """Identification and opt-out footer, always added by the server (never by templates/AI)."""
    link = unsubscribe_url(settings.api_public_url, message.unsubscribe_token or "")
    lines: list[str] = []
    sender = workspace_settings.sender_company if workspace_settings else None
    address = workspace_settings.business_address if workspace_settings else None
    if sender or address:
        lines.append(", ".join(part for part in (sender, address) if part))
    lines.append(f"Unsubscribe: {link}")
    return "\n".join(lines)


def text_to_html(text: str) -> str:
    """Plain, readable HTML: escaped paragraphs and clickable links, no tracking."""
    paragraphs = []
    for block in re.split(r"\n\s*\n", text.strip()):
        escaped = html.escape(block)
        linked = _URL_RE.sub(lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>', escaped)
        paragraphs.append("<p>" + linked.replace("\n", "<br>") + "</p>")
    return (
        '<!doctype html><html><body style="font-family:Arial,Helvetica,sans-serif;'
        'font-size:14px;line-height:1.5;color:#1f2933">' + "".join(paragraphs) + "</body></html>"
    )


def build_outbound(
    message: EmailMessage,
    *,
    from_email: str,
    workspace_settings: WorkspaceSettings | None,
    in_reply_to: str | None = None,
) -> OutboundEmail:
    """Build the provider payload. Requires ``message.rfc_message_id`` to be set."""
    token = message.unsubscribe_token or ""
    link = unsubscribe_url(settings.api_public_url, token)
    footer = _footer(message, workspace_settings)
    text = f"{message.body.rstrip()}\n\n--\n{footer}\n"

    list_unsubscribe = f"<{link}>"
    headers: dict[str, str] = {
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
    if settings.inbound_email_domain:
        list_unsubscribe += f", <mailto:unsubscribe+{token}@{settings.inbound_email_domain}>"
        if message.reply_token:
            headers["Reply-To"] = f"reply+{message.reply_token}@{settings.inbound_email_domain}"
    headers["List-Unsubscribe"] = list_unsubscribe
    if in_reply_to:
        headers["In-Reply-To"] = f"<{in_reply_to}>"
        headers["References"] = f"<{in_reply_to}>"

    return OutboundEmail(
        to=message.recipient_email,
        subject=message.subject,
        text=text,
        html=text_to_html(text),
        message_id=message.rfc_message_id or make_message_id(from_email),
        idempotency_key=message.idempotency_key or f"lg-{message.id}",
        correlation_id=str(message.id),
        headers=headers,
    )
