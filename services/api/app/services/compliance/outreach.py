from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.suppression import Suppression


def is_email_suppressed(db: Session, email: str) -> bool:
    domain = email.split("@")[-1].lower() if "@" in email else None
    clauses = [Suppression.email == email.lower()]
    if domain:
        clauses.append(Suppression.domain == domain)
    return db.scalar(select(Suppression.id).where(or_(*clauses)).limit(1)) is not None


def validate_lead_for_outreach(lead: Lead, db: Session) -> list[str]:
    errors: list[str] = []

    if not lead.source_url:
        errors.append("Lead is missing a source URL")
    if not lead.compliance_source_note:
        errors.append("Lead is missing a compliance/source note")

    active_contacts = [contact for contact in (lead.email_contacts or []) if not contact.opted_out]
    if not active_contacts:
        errors.append("Lead has no active email contact")

    for contact in active_contacts:
        if is_email_suppressed(db, contact.email):
            errors.append(f"Email {contact.email} is on the suppression list")
            break

    return errors


def primary_recipient_email(lead: Lead) -> str | None:
    active_contacts = [contact for contact in (lead.email_contacts or []) if not contact.opted_out]
    if not active_contacts:
        return None

    non_generic = [c for c in active_contacts if not c.is_role_based and c.is_personal]
    if non_generic:
        return non_generic[0].email

    role_based = [c for c in active_contacts if c.is_role_based]
    if role_based:
        return role_based[0].email

    return active_contacts[0].email
