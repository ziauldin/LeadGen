"""Verify email contacts, spend verification credits and expose the result to the send gate."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import QuotaExceededError
from app.models.email_contact import EmailContact
from app.models.enums import ProviderName, ProviderType
from app.models.workspace import Workspace, WorkspaceSettings
from app.services.billing.usage import check_quota, record_usage
from app.services.provider_credentials.service import (
    _as_str,
    decrypt_provider_config,
    get_active_credential,
)
from app.services.verification.providers import (
    INVALID,
    RISKY,
    DnsVerifier,
    MockVerifier,
    NeverBounceVerifier,
    Verifier,
    ZeroBounceVerifier,
)

logger = logging.getLogger(__name__)
REVERIFY_AFTER = timedelta(days=90)


def verifier_for(db: Session, workspace_id: int) -> Verifier:
    credential = get_active_credential(db, workspace_id, ProviderType.EMAIL_VERIFICATION)
    if credential is None:
        return DnsVerifier()
    name = ProviderName(_as_str(credential.provider_name))
    config = decrypt_provider_config(credential)
    if name == ProviderName.ZEROBOUNCE:
        return ZeroBounceVerifier(str(config.get("api_key", "")))
    if name == ProviderName.NEVERBOUNCE:
        return NeverBounceVerifier(str(config.get("api_key", "")))
    return MockVerifier()


@dataclass
class VerificationSummary:
    checked: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    out_of_credits: bool = False


def needs_check(contact: EmailContact, now: datetime) -> bool:
    if contact.verification_status is None or contact.verified_at is None:
        return True
    verified = (
        contact.verified_at
        if contact.verified_at.tzinfo
        else contact.verified_at.replace(tzinfo=UTC)
    )
    return verified < now - REVERIFY_AFTER


def verify_contacts(
    db: Session, workspace: Workspace, contacts: list[EmailContact], *, force: bool = False
) -> VerificationSummary:
    verifier = verifier_for(db, workspace.id)
    now = datetime.now(UTC)
    summary = VerificationSummary()
    for contact in contacts:
        if not force and not needs_check(contact, now):
            continue
        if verifier.name != "dns":
            try:
                check_quota(db, workspace, "monthly_verifications")
            except QuotaExceededError:
                summary.out_of_credits = True
                break
        result = verifier.verify(contact.email.strip().lower())
        contact.verification_status = result.status
        contact.verification_detail = result.detail[:255]
        contact.verification_provider = result.provider
        contact.verified_at = now
        contact.is_verified = result.status == "valid"
        if result.billable and verifier.name != "dns":
            record_usage(db, workspace.id, "monthly_verifications")
        summary.checked += 1
        summary.by_status[result.status] = summary.by_status.get(result.status, 0) + 1
    db.commit()
    return summary


def verify_leads(
    db: Session, workspace: Workspace, lead_ids: list[int], *, force: bool = False
) -> VerificationSummary:
    contacts = list(
        db.scalars(
            select(EmailContact).where(
                EmailContact.workspace_id == workspace.id,
                EmailContact.lead_id.in_(lead_ids),
                EmailContact.opted_out.is_(False),
            )
        ).all()
    )
    return verify_contacts(db, workspace, contacts, force=force)


def blocks_outreach(db: Session, workspace_id: int, contact: EmailContact) -> str | None:
    """Why this address mustn't be emailed, or None."""
    if contact.verification_status == INVALID:
        return f"Email {contact.email} failed verification ({contact.verification_detail or 'invalid'})"
    if contact.verification_status == RISKY:
        block_risky = db.scalar(
            select(WorkspaceSettings.block_risky_emails).where(
                WorkspaceSettings.workspace_id == workspace_id
            )
        )
        if block_risky:
            return f"Email {contact.email} is risky ({contact.verification_detail or 'catch-all'}) and risky addresses are blocked"
    return None


def queue_auto_verification(db: Session, workspace_id: int) -> bool:
    """Verify new contacts in the background, but only when a verification provider is connected."""
    if get_active_credential(db, workspace_id, ProviderType.EMAIL_VERIFICATION) is None:
        return False
    from app.workers.verification_jobs import verify_pending_task

    try:
        verify_pending_task.delay(workspace_id)
    except Exception:  # verification is best effort; the gate still blocks known-bad addresses
        logger.exception("Could not queue email verification")
        return False
    return True


def pending_contacts(db: Session, workspace_id: int, limit: int = 1000) -> list[EmailContact]:
    return list(
        db.scalars(
            select(EmailContact)
            .where(
                EmailContact.workspace_id == workspace_id,
                EmailContact.verification_status.is_(None),
                EmailContact.opted_out.is_(False),
            )
            .order_by(EmailContact.id)
            .limit(limit)
        ).all()
    )
