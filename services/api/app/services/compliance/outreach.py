import hashlib

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.suppression import Suppression
from app.models.workspace import WorkspaceSettings

LAWFUL_BASES = ("legitimate_interest", "consent", "contract")


def _domain_of(email: str) -> str | None:
    return email.rsplit("@", 1)[-1].lower() if "@" in email else None


def is_email_suppressed(db: Session, workspace_id: int, email: str) -> bool:
    """True if ``email`` is suppressed for this workspace or platform-wide.

    A row with an email blocks that address only. A row with only a domain (added manually)
    blocks the whole domain. Unsubscribes never create domain-wide rows.
    """
    normalized = email.strip().lower()
    domain = _domain_of(normalized)
    hashed = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    match = [Suppression.email == normalized, Suppression.email_hash == hashed]
    if domain:
        match.append(and_(Suppression.email.is_(None), Suppression.domain == domain))
    return (
        db.scalar(
            select(Suppression.id)
            .where(
                or_(Suppression.workspace_id == workspace_id, Suppression.workspace_id.is_(None)),
                or_(*match),
            )
            .limit(1),
        )
        is not None
    )


def validate_lead_for_outreach(lead: Lead, db: Session) -> list[str]:
    errors: list[str] = []

    if not lead.source_url:
        errors.append("Lead is missing a source URL")
    if not lead.compliance_source_note:
        errors.append("Lead is missing a compliance/source note")
    if lead.lawful_basis not in LAWFUL_BASES:
        errors.append("Lead has no lawful basis for contact")
    elif lead.lawful_basis == "legitimate_interest" and not lead.lawful_basis_note:
        require_note = db.scalar(
            select(WorkspaceSettings.require_lia_note).where(
                WorkspaceSettings.workspace_id == lead.workspace_id
            )
        )
        if require_note:
            errors.append("Lead needs a legitimate-interest note before outreach")

    active_contacts = [contact for contact in (lead.email_contacts or []) if not contact.opted_out]
    if not active_contacts:
        errors.append("Lead has no active email contact")

    for contact in active_contacts:
        if is_email_suppressed(db, lead.workspace_id, contact.email):
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
