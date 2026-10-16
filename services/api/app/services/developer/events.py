"""The ``data`` object sent with each outbound webhook event. Documented in docs/API.md."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.email_message import EmailMessage
from app.models.enrollment import CampaignEnrollment
from app.models.lead import Lead
from app.models.reply import Reply
from app.services.developer.webhooks import emit_event


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def lead_data(lead: Lead, emails: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": lead.id,
        "full_name": lead.full_name,
        "job_title": lead.job_title,
        "niche_id": lead.niche_id,
        "company_id": lead.company_id,
        "status": str(lead.status),
        "source_provider": lead.source_provider,
        "source_url": lead.source_url,
        "lawful_basis": lead.lawful_basis,
        "emails": emails or [],
    }


def message_data(message: EmailMessage) -> dict[str, Any]:
    return {
        "id": message.id,
        "lead_id": message.lead_id,
        "campaign_id": message.campaign_id,
        "step_number": message.step_number,
        "recipient_email": message.recipient_email,
        "subject": message.subject,
        "status": str(message.status),
        "sent_at": _iso(message.sent_at),
    }


def reply_data(reply: Reply) -> dict[str, Any]:
    return {
        "id": reply.id,
        "lead_id": reply.lead_id,
        "email_message_id": reply.email_message_id,
        "from_email": reply.from_email,
        "subject": reply.subject,
        "classification": str(reply.classification),
        "is_auto_reply": reply.is_auto_reply,
        "snippet": (reply.body or "")[:280],
        "received_at": _iso(reply.received_at),
    }


def enrollment_data(enrollment: CampaignEnrollment) -> dict[str, Any]:
    return {
        "id": enrollment.id,
        "campaign_id": enrollment.campaign_id,
        "lead_id": enrollment.lead_id,
        "status": str(enrollment.status),
        "current_step": enrollment.current_step,
    }


def lead_created(db: Session, lead: Lead, emails: list[str] | None = None) -> None:
    emit_event(db, lead.workspace_id, "lead.created", {"lead": lead_data(lead, emails)})


def email_sent(db: Session, message: EmailMessage) -> None:
    emit_event(db, message.workspace_id, "email.sent", {"email": message_data(message)})


def email_bounced(db: Session, message: EmailMessage, kind: str) -> None:
    emit_event(
        db, message.workspace_id, "email.bounced", {"email": message_data(message), "kind": kind}
    )


def reply_received(db: Session, reply: Reply) -> None:
    emit_event(db, reply.workspace_id, "reply.received", {"reply": reply_data(reply)})


def enrollment_completed(db: Session, enrollment: CampaignEnrollment) -> None:
    emit_event(
        db,
        enrollment.workspace_id,
        "enrollment.completed",
        {"enrollment": enrollment_data(enrollment)},
    )
