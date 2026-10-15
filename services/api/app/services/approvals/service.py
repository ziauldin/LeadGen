"""The approval queue: every email waits here until a person approves, edits or rejects it."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError, NotFoundError, ValidationFailedError
from app.models.campaign import Campaign
from app.models.email_message import EmailMessage
from app.models.enrollment import CampaignEnrollment, EnrollmentStatus
from app.models.enums import EmailMessageStatus
from app.models.lead import Lead
from app.schemas.common import BulkResult
from app.services.campaigns.sequences import stop_enrollment
from app.services.compliance.outreach import validate_lead_for_outreach
from app.services.email_generation.generator import approve_email_message, has_opt_out_line
from app.services.sending.state import REVIEWABLE, InvalidTransitionError, transition
from app.services.workspaces.service import audit

MAX_SUBJECT = 500
MAX_BODY = 20_000


def queue_query(workspace_id: int, *, campaign_id: int | None, mode: str | None):
    query = select(EmailMessage).where(
        EmailMessage.workspace_id == workspace_id,
        EmailMessage.status.in_(list(REVIEWABLE)),
    )
    if campaign_id is not None:
        query = query.where(EmailMessage.campaign_id == campaign_id)
    if mode:
        query = query.where(EmailMessage.generation_mode == mode)
    return query


def queue_counts(db: Session, workspace_id: int) -> dict[str, int]:
    rows = db.execute(
        select(EmailMessage.campaign_id, func.count(EmailMessage.id))
        .where(
            EmailMessage.workspace_id == workspace_id,
            EmailMessage.status.in_(list(REVIEWABLE)),
        )
        .group_by(EmailMessage.campaign_id),
    ).all()
    return {str(campaign_id or "none"): count for campaign_id, count in rows}


def review_problems(db: Session, message: EmailMessage, lead: Lead | None) -> list[str]:
    """What would stop this email being approved right now."""
    if lead is None:
        return ["Lead not found"]
    problems = validate_lead_for_outreach(lead, db)
    if not has_opt_out_line(message.body):
        problems.append("Email is missing a required opt-out line")
    return problems


def load_reviewable(db: Session, workspace_id: int, message_id: int) -> EmailMessage:
    message = db.scalar(
        select(EmailMessage)
        .where(EmailMessage.id == message_id, EmailMessage.workspace_id == workspace_id)
        .options(
            selectinload(EmailMessage.lead).selectinload(Lead.email_contacts),
            selectinload(EmailMessage.lead).selectinload(Lead.company),
        ),
    )
    if message is None:
        raise NotFoundError("Email message not found")
    return message


def edit_message(
    db: Session,
    workspace_id: int,
    message_id: int,
    *,
    subject: str | None,
    body: str | None,
    actor_id: int | None,
) -> EmailMessage:
    message = load_reviewable(db, workspace_id, message_id)
    if message.status not in REVIEWABLE:
        raise ValidationFailedError("Only drafts waiting for approval can be edited")
    new_subject = (subject if subject is not None else message.subject).strip()
    new_body = body if body is not None else message.body
    if not new_subject or len(new_subject) > MAX_SUBJECT:
        raise ValidationFailedError(f"The subject must be 1-{MAX_SUBJECT} characters")
    if not new_body.strip() or len(new_body) > MAX_BODY:
        raise ValidationFailedError(f"The body must be 1-{MAX_BODY} characters")
    if not has_opt_out_line(new_body):
        raise ValidationFailedError(
            "Keep the opt-out line: recipients must be able to say no to further emails",
        )
    changed = [
        name
        for name, old, new in (
            ("subject", message.subject, new_subject),
            ("body", message.body, new_body),
        )
        if old != new
    ]
    if not changed:
        return message
    message.subject = new_subject
    message.body = new_body
    message.edited_by = actor_id
    message.edited_at = datetime.now(UTC)
    audit(
        db, workspace_id, actor_id, "email.edited", "email_message", message.id, {"fields": changed}
    )
    db.commit()
    db.refresh(message)
    return message


def reject_message(
    db: Session,
    workspace_id: int,
    message_id: int,
    *,
    reason: str | None,
    actor_id: int | None,
    commit: bool = True,
) -> EmailMessage:
    """Reject a draft. In a sequence, rejecting also stops that lead's sequence."""
    message = load_reviewable(db, workspace_id, message_id)
    if message.status not in REVIEWABLE:
        raise ValidationFailedError("Only drafts waiting for approval can be rejected")
    note = (reason or "Rejected in review").strip()[:500]
    transition(db, message, EmailMessageStatus.REJECTED, actor_id=actor_id, reason=note)
    message.rejected_reason = note
    if message.enrollment_id:
        enrollment = db.get(CampaignEnrollment, message.enrollment_id)
        if enrollment is not None:
            stop_enrollment(db, enrollment, EnrollmentStatus.STOPPED, f"Draft rejected: {note}")
    if commit:
        db.commit()
        db.refresh(message)
    return message


def bulk_approve(
    db: Session,
    workspace_id: int,
    message_ids: list[int],
    *,
    actor_id: int | None,
) -> BulkResult:
    result = BulkResult()
    for message_id in dict.fromkeys(message_ids):
        try:
            approve_email_message(db, message_id, workspace_id, actor_id=actor_id)
        except (AppError, InvalidTransitionError) as exc:
            db.rollback()
            detail = getattr(exc, "detail", None) or str(exc)
            if isinstance(exc, NotFoundError):
                result.skip(message_id, str(detail))
            else:
                result.fail(message_id, str(detail))
            continue
        result.ok(message_id)
    _audit_bulk(db, workspace_id, actor_id, "email.bulk_approved", result)
    return result


def bulk_reject(
    db: Session,
    workspace_id: int,
    message_ids: list[int],
    *,
    reason: str | None,
    actor_id: int | None,
) -> BulkResult:
    result = BulkResult()
    for message_id in dict.fromkeys(message_ids):
        try:
            reject_message(db, workspace_id, message_id, reason=reason, actor_id=actor_id)
        except (AppError, InvalidTransitionError) as exc:
            db.rollback()
            detail = getattr(exc, "detail", None) or str(exc)
            if isinstance(exc, NotFoundError):
                result.skip(message_id, str(detail))
            else:
                result.fail(message_id, str(detail))
            continue
        result.ok(message_id)
    _audit_bulk(db, workspace_id, actor_id, "email.bulk_rejected", result)
    return result


def _audit_bulk(
    db: Session,
    workspace_id: int,
    actor_id: int | None,
    action: str,
    result: BulkResult,
) -> None:
    audit(
        db,
        workspace_id,
        actor_id,
        action,
        "email_message",
        None,
        {"succeeded": result.succeeded, "failed": result.failed, "skipped": result.skipped},
    )
    db.commit()


def campaign_names(db: Session, campaign_ids: set[int]) -> dict[int, str]:
    if not campaign_ids:
        return {}
    return dict(
        db.execute(select(Campaign.id, Campaign.name).where(Campaign.id.in_(campaign_ids))).all(),
    )
