from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.tenancy import bind_session, system_session
from app.models.audit_log import AuditLog
from app.models.email_contact import EmailContact
from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus, LeadStatus
from app.models.lead import Lead
from app.models.suppression import Suppression


def find_message_by_unsubscribe_token(db: Session, token: str) -> EmailMessage | None:
    """Find the email an unsubscribe token belongs to.

    From a public link the session isn't scoped yet: the token identifies the workspace, so
    look it up across workspaces and then scope the session to it. A session that is already
    scoped (inbound processing) only searches its own workspace.
    """
    if not token or len(token) > 128:
        return None
    query = select(EmailMessage).where(EmailMessage.unsubscribe_token == token)
    if db.info.get("workspace_id") is not None or db.info.get("tenant_bypass"):
        return db.scalar(query)
    with system_session(db):
        message = db.scalar(query)
    if message is not None:
        bind_session(db, message.workspace_id)
    return message


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
    reason_code: str = "manual",
    email_message_id: int | None = None,
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

    db.flush()
    existing = db.scalar(
        select(Suppression).where(
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
                reason_code=reason_code,
                source=source,
                email_message_id=email_message_id,
            ),
        )
    else:
        existing.reason_code = existing.reason_code or reason_code
        existing.email_message_id = existing.email_message_id or email_message_id


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
        reason_code="unsubscribe",
        email_message_id=message.id,
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
