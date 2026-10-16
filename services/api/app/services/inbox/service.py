"""The unified inbox: conversations built from replies, threaded timelines, replying from the
app through the original mailbox, assignment, snoozing, labels and AI reply suggestions."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.core.flags import feature_enabled
from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus, LeadStatus
from app.models.inbox import Conversation
from app.models.lead import Lead
from app.models.reply import Reply
from app.models.workspace import Workspace, WorkspaceSettings
from app.services.billing.usage import check_quota, record_usage
from app.services.compliance.outreach import is_email_suppressed
from app.services.workspaces.service import audit

SENT_LIKE = (EmailMessageStatus.SENT, EmailMessageStatus.BOUNCED, EmailMessageStatus.COMPLAINED)
STATUSES = ("open", "snoozed", "done")
MAX_LABELS = 10


def _now() -> datetime:
    return datetime.now(UTC)


def conversation_for(
    db: Session, workspace_id: int, lead_id: int | None, email: str
) -> Conversation:
    email = email.strip().lower()
    query = select(Conversation).where(Conversation.workspace_id == workspace_id)
    query = (
        query.where(Conversation.lead_id == lead_id)
        if lead_id
        else query.where(Conversation.lead_id.is_(None), Conversation.contact_email == email)
    )
    conversation = db.scalar(query)
    if conversation is None:
        conversation = Conversation(
            workspace_id=workspace_id, lead_id=lead_id, contact_email=email, labels=[]
        )
        db.add(conversation)
        db.flush()
    return conversation


def on_reply(db: Session, reply: Reply) -> Conversation:
    """A new inbound message: (re)open the person's conversation and mark it unread."""
    conversation = conversation_for(db, reply.workspace_id, reply.lead_id, reply.from_email)
    received = reply.received_at
    if conversation.last_message_at is None or _aware(received) >= _aware(
        conversation.last_message_at
    ):
        conversation.last_message_at = received
        conversation.subject = reply.subject or conversation.subject
        conversation.last_classification = str(reply.classification)
    conversation.last_inbound_at = received
    if not reply.is_auto_reply:
        conversation.status = "open"
        conversation.snoozed_until = None
        conversation.unread = True
    return conversation


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def backfill(db: Session, workspace_id: int) -> int:
    """Create conversations for replies that arrived before the inbox existed."""
    existing_leads = select(Conversation.lead_id).where(
        Conversation.workspace_id == workspace_id, Conversation.lead_id.is_not(None)
    )
    existing_emails = select(Conversation.contact_email).where(
        Conversation.workspace_id == workspace_id, Conversation.lead_id.is_(None)
    )
    missing = db.scalars(
        select(Reply)
        .where(
            Reply.workspace_id == workspace_id,
            or_(
                Reply.lead_id.not_in(existing_leads),
                (Reply.lead_id.is_(None) & Reply.from_email.not_in(existing_emails)),
            ),
        )
        .order_by(Reply.received_at)
    ).all()
    for reply in missing:
        on_reply(db, reply)
    if missing:
        db.commit()
    return len(missing)


def get(db: Session, workspace_id: int, conversation_id: int) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.workspace_id == workspace_id
        )
    )
    if conversation is None:
        raise NotFoundError("Conversation not found")
    return conversation


@dataclass
class ThreadItem:
    kind: str  # "sent" | "received"
    id: int
    at: datetime
    subject: str | None
    body: str
    from_email: str | None
    to_email: str | None
    status: str | None
    classification: str | None
    campaign_id: int | None


def thread(db: Session, conversation: Conversation) -> list[ThreadItem]:
    items: list[ThreadItem] = []
    reply_filter = (
        Reply.lead_id == conversation.lead_id
        if conversation.lead_id
        else (Reply.lead_id.is_(None) & (Reply.from_email == conversation.contact_email))
    )
    for reply in db.scalars(
        select(Reply).where(Reply.workspace_id == conversation.workspace_id, reply_filter)
    ).all():
        items.append(
            ThreadItem(
                "received",
                reply.id,
                reply.received_at,
                reply.subject,
                reply.body,
                reply.from_email,
                None,
                None,
                str(reply.classification),
                None,
            )
        )
    if conversation.lead_id:
        for message in db.scalars(
            select(EmailMessage).where(
                EmailMessage.workspace_id == conversation.workspace_id,
                EmailMessage.lead_id == conversation.lead_id,
                EmailMessage.status.in_(SENT_LIKE),
            )
        ).all():
            items.append(
                ThreadItem(
                    "sent",
                    message.id,
                    message.sent_at or message.created_at,
                    message.subject,
                    message.body,
                    None,
                    message.recipient_email,
                    str(message.status),
                    None,
                    message.campaign_id,
                )
            )
    items.sort(key=lambda item: _aware(item.at))
    return items


def update_conversation(
    db: Session,
    conversation: Conversation,
    *,
    actor_id: int,
    changes: dict[str, Any],
) -> Conversation:
    if "status" in changes:
        status = changes["status"]
        if status not in STATUSES:
            raise ValidationFailedError("Unknown status")
        conversation.status = status
        if status != "snoozed":
            conversation.snoozed_until = None
    if "snoozed_until" in changes:
        until = changes["snoozed_until"]
        if until is not None:
            if _aware(until) <= _now():
                raise ValidationFailedError("Snooze until a time in the future")
            conversation.status = "snoozed"
        conversation.snoozed_until = until
    if "assignee_id" in changes:
        conversation.assignee_id = changes["assignee_id"]
    if "labels" in changes:
        labels = sorted({label.strip()[:30] for label in changes["labels"] if label.strip()})
        if len(labels) > MAX_LABELS:
            raise ValidationFailedError(f"Use at most {MAX_LABELS} labels")
        conversation.labels = labels
    if "unread" in changes:
        conversation.unread = bool(changes["unread"])
    audit(
        db,
        conversation.workspace_id,
        actor_id,
        "conversation_updated",
        "conversation",
        conversation.id,
        {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in changes.items()},
    )
    db.commit()
    return conversation


def wake_snoozed(db: Session) -> int:
    result = db.execute(
        update(Conversation)
        .where(Conversation.status == "snoozed", Conversation.snoozed_until <= _now())
        .values(status="open", snoozed_until=None, unread=True)
    )
    db.commit()
    return result.rowcount or 0  # type: ignore[attr-defined]


def send_reply(
    db: Session, workspace: Workspace, actor_id: int, conversation: Conversation, body: str
) -> EmailMessage:
    """Reply to the person's last message, from the mailbox that emailed them, in the same thread."""
    from app.services.developer import events as webhook_events
    from app.services.sending.base import SendKind
    from app.services.sending.mime import build_outbound
    from app.services.sending.provider_factory import resolve_sender
    from app.services.sending.sender import _ensure_identifiers
    from app.services.sending.state import transition

    if conversation.lead_id is None:
        raise ValidationFailedError("Link this conversation to a lead before replying")
    lead = db.get(Lead, conversation.lead_id)
    if lead is None:
        raise NotFoundError("Lead not found")
    last_inbound = db.scalar(
        select(Reply)
        .where(Reply.workspace_id == workspace.id, Reply.lead_id == lead.id)
        .order_by(Reply.received_at.desc())
        .limit(1)
    )
    recipient = (
        (last_inbound.from_email if last_inbound else conversation.contact_email).strip().lower()
    )
    if lead.status == LeadStatus.OPTED_OUT or is_email_suppressed(db, workspace.id, recipient):
        raise ValidationFailedError("This person asked not to be contacted")
    check_quota(db, workspace, "monthly_sends")

    last_outbound = db.scalar(
        select(EmailMessage)
        .where(EmailMessage.lead_id == lead.id, EmailMessage.status.in_(SENT_LIKE))
        .order_by(EmailMessage.sent_at.desc())
        .limit(1)
    )
    sender, credential = resolve_sender(
        db, workspace.id, last_outbound.sender_credential_id if last_outbound else None
    )
    subject = (
        (last_inbound.subject if last_inbound else None) or conversation.subject or "Your message"
    )
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    message = EmailMessage(
        workspace_id=workspace.id,
        lead_id=lead.id,
        campaign_id=last_outbound.campaign_id if last_outbound else None,
        recipient_email=recipient,
        subject=subject[:500],
        body=body.strip(),
        status=EmailMessageStatus.APPROVED,
        unsubscribe_token=secrets.token_urlsafe(24),
        generation_mode="manual",
    )
    db.add(message)
    db.flush()
    _ensure_identifiers(message, sender.from_email)
    message.sender_credential_id = credential.id if credential else None
    settings_row = db.scalar(
        select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == workspace.id)
    )
    outbound = build_outbound(
        message,
        from_email=sender.from_email,
        workspace_settings=settings_row,
        in_reply_to=last_inbound.message_id_header.strip("<>")
        if last_inbound and last_inbound.message_id_header
        else None,
    )
    result = sender.send(outbound)
    if result.kind != SendKind.OK:
        transition(db, message, EmailMessageStatus.FAILED, actor_id=actor_id, reason=result.error)
        message.last_error = result.error
        db.commit()
        raise ValidationFailedError(
            f"The email couldn't be sent: {result.error or 'provider error'}"
        )
    for step in (EmailMessageStatus.QUEUED, EmailMessageStatus.SENDING):
        transition(db, message, step, audit=False)
    transition(db, message, EmailMessageStatus.SENT, actor_id=actor_id, reason="inbox reply")
    message.sent_at = _now()
    message.provider_message_id = result.provider_message_id
    record_usage(db, workspace.id, "monthly_sends")
    webhook_events.email_sent(db, message)
    conversation.last_message_at = message.sent_at
    conversation.unread = False
    audit(
        db,
        workspace.id,
        actor_id,
        "inbox_reply_sent",
        "conversation",
        conversation.id,
        {"email_message_id": message.id},
    )
    db.commit()
    return message


def suggest_reply(
    db: Session, workspace: Workspace, actor_id: int, conversation: Conversation
) -> str:
    """An AI draft for a person to edit and send. Never sent automatically."""
    from app.services.llm.factory import run_llm

    settings_row = db.scalar(
        select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == workspace.id)
    )
    if (
        not feature_enabled("ai_emails", workspace)
        or settings_row is None
        or settings_row.ai_mode == "off"
    ):
        raise ValidationFailedError("Turn on AI writing in Settings to get reply suggestions")
    items = thread(db, conversation)[-6:]
    transcript = "\n\n".join(
        f"{'We wrote' if item.kind == 'sent' else 'They wrote'} ({_aware(item.at).date()}):\n{item.body[:1500]}"
        for item in items
    )
    result = run_llm(
        db,
        workspace,
        purpose="inbox_suggestion",
        system=(
            "You help a salesperson reply to a prospect. Write a short, friendly, specific reply in plain text "
            "(no subject line, no signature). Answer their questions using only the product facts provided. "
            "If they asked not to be contacted, write a brief apology confirming they won't hear from us again."
        ),
        user=(
            f"Product facts:\n{settings_row.product_description or 'Not provided'}\n\n"
            f"Tone: {settings_row.tone_guidelines or 'warm, concise, professional'}\n\nConversation:\n{transcript}"
        ),
        max_tokens=400,
        json_mode=False,
        user_id=actor_id,
    )
    db.commit()
    return result.text.strip()
