from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.email_contact import EmailContact
from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus, LeadStatus
from app.models.lead import Lead
from app.models.suppression import Suppression


def find_message_by_unsubscribe_token(db: Session, token: str) -> EmailMessage | None:
    if not token or len(token) > 128:
        return None
    return db.scalar(select(EmailMessage).where(EmailMessage.unsubscribe_token == token))


def cancel_pending_messages(db: Session, *, workspace_id: int, email: str, reason: str) -> int:
    """Cancel every not-yet-sent email to this address in the workspace."""
    from app.services.sending.state import CANCELLABLE, transition

    pending = db.scalars(
        select(EmailMessage).where(
            EmailMessage.workspace_id == workspace_id,
            func.lower(EmailMessage.recipient_email) == email,
            EmailMessage.status.in_(list(CANCELLABLE)),
        ),
    ).all()
    for message in pending:
        transition(db, message, EmailMessageStatus.CANCELLED, reason=reason)
        message.failure_reason = f"Cancelled: {reason}"
    return len(pending)


def suppress_email(
    db: Session,
    *,
    workspace_id: int,
    email: str,
    reason: str,
    source: str,
    lead_id: int | None = None,
) -> None:
    """Suppress one address in a workspace and opt out its contacts and lead.

    Only the address itself is suppressed, never the whole domain.
    """
    normalized = email.strip().lower()
    for contact in db.scalars(
        select(EmailContact).where(
            EmailContact.workspace_id == workspace_id,
            EmailContact.email == normalized,
        ),
    ).all():
        contact.opted_out = True

    if lead_id is not None:
        lead = db.get(Lead, lead_id)
        if lead is not None and lead.workspace_id == workspace_id:
            lead.status = LeadStatus.OPTED_OUT
            lead.score = 0.0

    from app.models.enrollment import EnrollmentStatus
    from app.services.campaigns.sequences import stop_enrollments_for_email

    stop_enrollments_for_email(
        db,
        workspace_id=workspace_id,
        email=normalized,
        status=EnrollmentStatus.OPTED_OUT,
        reason=reason,
    )
    cancel_pending_messages(db, workspace_id=workspace_id, email=normalized, reason=reason)

    existing = db.scalar(
        select(Suppression.id).where(
            Suppression.workspace_id == workspace_id,
            Suppression.email == normalized,
        ),
    )
    if existing is None:
        db.add(
            Suppression(
                workspace_id=workspace_id,
                email=normalized,
                domain=None,
                reason=reason,
                source=source,
            ),
        )


def process_unsubscribe_for_message(db: Session, token: str) -> EmailMessage | None:
    message = find_message_by_unsubscribe_token(db, token)
    if message is None:
        return None

    suppress_email(
        db,
        workspace_id=message.workspace_id,
        email=message.recipient_email,
        reason="unsubscribe",
        source="unsubscribe_link",
        lead_id=message.lead_id,
    )
    db.add(
        AuditLog(
            workspace_id=message.workspace_id,
            actor_id=None,
            action="unsubscribe",
            entity_type="email_message",
            entity_id=message.id,
            metadata_={"lead_id": message.lead_id},
        ),
    )
    db.commit()
    return message
