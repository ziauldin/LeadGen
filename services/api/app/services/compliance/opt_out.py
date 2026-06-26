from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.email_contact import EmailContact
from app.models.email_message import EmailMessage
from app.models.enums import LeadStatus
from app.models.lead import Lead
from app.models.suppression import Suppression


def process_unsubscribe_for_message(db: Session, token: str) -> EmailMessage | None:
    message = db.scalar(select(EmailMessage).where(EmailMessage.unsubscribe_token == token))
    if message is None:
        return None

    contact = db.scalar(select(EmailContact).where(EmailContact.email == message.recipient_email))
    if contact:
        contact.opted_out = True

    lead = db.get(Lead, message.lead_id)
    if lead:
        lead.status = LeadStatus.OPTED_OUT
        lead.score = 0.0

    domain = message.recipient_email.split("@")[-1].lower() if "@" in message.recipient_email else None
    existing = db.scalar(select(Suppression).where(Suppression.email == message.recipient_email.lower()))
    if existing is None:
        db.add(
            Suppression(
                email=message.recipient_email.lower(),
                domain=domain,
                reason="unsubscribe",
                source="unsubscribe_link",
            ),
        )

    db.add(
        AuditLog(
            actor_id=None,
            action="unsubscribe",
            entity_type="email_message",
            entity_id=message.id,
            metadata_={
                "recipient_email": message.recipient_email,
                "lead_id": message.lead_id,
            },
        ),
    )

    db.commit()
    return message
