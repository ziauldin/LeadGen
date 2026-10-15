from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.audit_log import AuditLog
from app.models.campaign import Campaign
from app.models.email_message import EmailMessage
from app.models.enums import CampaignStatus, EmailMessageStatus, LeadStatus
from app.models.lead import Lead
from app.services.billing.usage import record_usage
from app.services.sending.gate import evaluate_send_gate
from app.services.sending.provider_factory import get_email_sender_for_workspace


def _log_audit(
    db: Session,
    workspace_id: int,
    actor_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int,
    metadata: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            workspace_id=workspace_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_=metadata,
        ),
    )


def send_email_message(db: Session, message_id: int, actor_id: int | None = None) -> EmailMessage:
    message = db.scalar(
        select(EmailMessage)
        .where(EmailMessage.id == message_id)
        .options(
            selectinload(EmailMessage.lead).selectinload(Lead.email_contacts),
            selectinload(EmailMessage.campaign),
        ),
    )
    if message is None:
        raise ValueError("Email message not found")

    if message.status == EmailMessageStatus.SENT:
        return message

    campaign = message.campaign
    if campaign is None:
        raise ValueError("Email message is not linked to a campaign")

    lead = message.lead
    if lead is None:
        raise ValueError("Lead not found for email message")

    gate = evaluate_send_gate(db, campaign, message, lead)
    if not gate.allowed:
        message.status = EmailMessageStatus.FAILED
        db.commit()
        _log_audit(
            db,
            message.workspace_id,
            actor_id,
            "email_send_blocked",
            "email_message",
            message.id,
            {"reasons": gate.reasons},
        )
        db.commit()
        raise ValueError("; ".join(gate.reasons))

    sender = get_email_sender_for_workspace(db, message.workspace_id)
    result = sender.send(message.recipient_email, message.subject, message.body)
    if not result.success:
        message.status = EmailMessageStatus.FAILED
        db.commit()
        _log_audit(
            db,
            message.workspace_id,
            actor_id,
            "email_send_failed",
            "email_message",
            message.id,
            {"error": result.error},
        )
        db.commit()
        raise ValueError(result.error or "Send failed")

    message.status = EmailMessageStatus.SENT
    message.sent_at = datetime.now(UTC)
    record_usage(db, message.workspace_id, "monthly_sends")
    message.provider_message_id = result.provider_message_id

    if lead.status not in {LeadStatus.REPLIED, LeadStatus.MEETING_BOOKED, LeadStatus.CLIENT}:
        lead.status = LeadStatus.CONTACTED

    _log_audit(
        db,
        message.workspace_id,
        actor_id,
        "email_sent",
        "email_message",
        message.id,
        {
            "provider": sender.provider_name,
            "provider_message_id": result.provider_message_id,
            "recipient_email": message.recipient_email,
        },
    )
    db.commit()
    db.refresh(message)
    return message


def process_active_campaigns(
    db: Session,
    actor_id: int | None = None,
    *,
    workspace_id: int | None = None,
    campaign_id: int | None = None,
) -> dict[str, int]:
    query = select(Campaign).where(Campaign.status == CampaignStatus.ACTIVE)
    if workspace_id is not None:
        query = query.where(Campaign.workspace_id == workspace_id)
    if campaign_id is not None:
        query = query.where(Campaign.id == campaign_id)
    campaigns = db.scalars(query).all()

    sent = 0
    failed = 0
    skipped = 0

    for campaign in campaigns:
        messages = db.scalars(
            select(EmailMessage)
            .where(
                EmailMessage.campaign_id == campaign.id,
                EmailMessage.status == EmailMessageStatus.APPROVED,
            )
            .order_by(EmailMessage.id.asc()),
        ).all()

        for message in messages:
            try:
                send_email_message(db, message.id, actor_id=actor_id)
                sent += 1
            except ValueError as exc:
                if "limit reached" in str(exc).lower() or "outside" in str(exc).lower():
                    skipped += 1
                    break
                failed += 1

    return {"sent": sent, "failed": failed, "skipped": skipped}
