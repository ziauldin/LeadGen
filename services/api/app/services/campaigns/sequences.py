"""Multi-step sequences: enrollments, follow-up drafts, stop conditions and completion.

Follow-ups are created as ``pending_approval`` drafts: a person always approves every email
before it can be sent. Drafts are scheduled for the step's delay, aligned to the campaign's
sending window, and created up to a day ahead so reviewers have time to approve them.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.tenancy import system_session
from app.models.campaign import Campaign, CampaignStep
from app.models.email_message import EmailMessage
from app.models.enrollment import CampaignEnrollment, EnrollmentStatus
from app.models.enums import CampaignStatus, EmailMessageStatus
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.workspace import Workspace, WorkspaceSettings
from app.services.compliance.outreach import primary_recipient_email, validate_lead_for_outreach
from app.services.email_generation.generator import (
    apply_content,
    build_content,
    has_opt_out_line,
    link_llm_usage,
)
from app.services.sending.schedule import schedule_for
from app.services.sending.state import CANCELLABLE, transition

logger = logging.getLogger(__name__)

DRAFT_LOOKAHEAD = timedelta(hours=24)
COMPLETION_GRACE = timedelta(days=3)
ACTIVE_MESSAGE_STATES = (
    EmailMessageStatus.DRAFT,
    EmailMessageStatus.PENDING_APPROVAL,
    EmailMessageStatus.APPROVED,
    EmailMessageStatus.QUEUED,
    EmailMessageStatus.SENDING,
)


class StepRenderError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _workspace_settings(db: Session, workspace_id: int) -> WorkspaceSettings | None:
    return db.scalar(
        select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == workspace_id)
    )


def sorted_steps(campaign: Campaign) -> list[CampaignStep]:
    return sorted(campaign.steps, key=lambda step: step.step_number)


def next_step_after(campaign: Campaign, step_number: int) -> CampaignStep | None:
    for step in sorted_steps(campaign):
        if step.step_number > step_number:
            return step
    return None


def _first_subject(db: Session, enrollment: CampaignEnrollment) -> str | None:
    return db.scalar(
        select(EmailMessage.subject)
        .where(EmailMessage.enrollment_id == enrollment.id)
        .order_by(EmailMessage.step_number.asc())
        .limit(1),
    )


def render_step_message(
    db: Session,
    *,
    campaign: Campaign,
    step: CampaignStep,
    lead: Lead,
    enrollment: CampaignEnrollment,
    sender_fallback_name: str,
    status: EmailMessageStatus,
    scheduled_for: datetime | None = None,
) -> EmailMessage:
    """Render one step for one lead and add it as a new message (flushes, no commit)."""
    errors = validate_lead_for_outreach(lead, db)
    if errors:
        raise StepRenderError("; ".join(errors))

    niche = db.get(Niche, campaign.niche_id)
    if niche is None:
        raise StepRenderError("Niche not found")
    token = secrets.token_urlsafe(32)
    first = _first_subject(db, enrollment) if step.step_number > 1 else None
    content = build_content(
        db,
        workspace_id=campaign.workspace_id,
        lead=lead,
        niche=niche,
        sender_fallback_name=sender_fallback_name,
        unsubscribe_token=token,
        template_id=step.template_id,
        subject_template=step.subject_template,
        body_template=step.body_template,
        mode="ai" if step.use_ai else "template",
        instructions=step.ai_instructions,
        step_number=step.step_number,
        previous_subject=first,
    )
    if step.step_number > 1 and step.thread_with_previous and first:
        content.subject = first if first.lower().startswith("re:") else f"Re: {first}"
    if not has_opt_out_line(content.body):
        raise StepRenderError("generated email missing opt-out line")

    recipient = primary_recipient_email(lead) or enrollment.recipient_email
    message = EmailMessage(
        workspace_id=campaign.workspace_id,
        campaign_id=campaign.id,
        lead_id=lead.id,
        enrollment_id=enrollment.id,
        campaign_step_id=step.id,
        step_number=step.step_number,
        recipient_email=recipient,
        recipient_domain=recipient.rsplit("@", 1)[-1].lower() if "@" in recipient else None,
        subject="",
        body="",
        status=status,
        scheduled_for=scheduled_for,
        unsubscribe_token=token,
    )
    apply_content(message, content)
    db.add(message)
    db.flush()
    link_llm_usage(db, message)
    return message


def enroll_lead(
    db: Session,
    *,
    campaign: Campaign,
    lead: Lead,
    sender_fallback_name: str,
) -> EmailMessage:
    """Create the enrollment and its step-1 draft. Raises StepRenderError if not eligible."""
    steps = sorted_steps(campaign)
    if not steps:
        raise StepRenderError("Campaign has no steps configured")
    recipient = primary_recipient_email(lead)
    if recipient is None:
        raise StepRenderError("Lead has no active email contact")

    enrollment = CampaignEnrollment(
        workspace_id=campaign.workspace_id,
        campaign_id=campaign.id,
        lead_id=lead.id,
        recipient_email=recipient,
        status=EnrollmentStatus.ACTIVE,
        current_step=0,
        next_step_number=steps[0].step_number,
    )
    db.add(enrollment)
    db.flush()
    try:
        return render_step_message(
            db,
            campaign=campaign,
            step=steps[0],
            lead=lead,
            enrollment=enrollment,
            sender_fallback_name=sender_fallback_name,
            status=EmailMessageStatus.DRAFT,
        )
    except StepRenderError:
        db.delete(enrollment)
        db.flush()
        raise


def _due_time(
    campaign: Campaign,
    workspace: Workspace | None,
    workspace_settings: WorkspaceSettings | None,
    last_sent_at: datetime,
    delay_days: int,
) -> datetime:
    schedule = schedule_for(campaign, workspace, workspace_settings)
    return schedule.next_open(last_sent_at + timedelta(days=delay_days))


def on_message_sent(db: Session, message: EmailMessage, sent_at: datetime) -> None:
    """Advance the enrollment after one of its emails went out."""
    if message.enrollment_id is None:
        return
    enrollment = db.get(CampaignEnrollment, message.enrollment_id)
    campaign = db.scalar(
        select(Campaign)
        .where(Campaign.id == message.campaign_id)
        .options(selectinload(Campaign.steps)),
    )
    if enrollment is None or campaign is None:
        return
    enrollment.current_step = max(enrollment.current_step, message.step_number or 1)
    enrollment.last_sent_at = sent_at
    following = next_step_after(campaign, enrollment.current_step)
    if following is None or enrollment.status != EnrollmentStatus.ACTIVE:
        enrollment.next_step_number = None
        enrollment.next_send_at = None
        return
    enrollment.next_step_number = following.step_number
    workspace = db.get(Workspace, campaign.workspace_id)
    enrollment.next_send_at = _due_time(
        campaign,
        workspace,
        _workspace_settings(db, campaign.workspace_id),
        sent_at,
        following.delay_days,
    )


def stop_enrollment(
    db: Session,
    enrollment: CampaignEnrollment,
    status: EnrollmentStatus,
    reason: str,
) -> int:
    """Stop a sequence and cancel its unsent emails. Returns the number cancelled."""
    if enrollment.status not in {EnrollmentStatus.ACTIVE, EnrollmentStatus.PAUSED}:
        return 0
    db.flush()  # the session doesn't autoflush; see status changes made just before this call
    enrollment.status = status
    enrollment.stopped_reason = reason[:255]
    enrollment.next_step_number = None
    enrollment.next_send_at = None
    cancelled = 0
    for message in db.scalars(
        select(EmailMessage).where(
            EmailMessage.enrollment_id == enrollment.id,
            EmailMessage.status.in_(list(CANCELLABLE)),
        ),
    ).all():
        transition(db, message, EmailMessageStatus.CANCELLED, reason=reason)
        message.failure_reason = f"Sequence stopped: {reason}"[:255]
        cancelled += 1
    return cancelled


def stop_enrollments_for_email(
    db: Session,
    *,
    workspace_id: int,
    email: str,
    status: EnrollmentStatus,
    reason: str,
    campaign_id: int | None = None,
) -> int:
    query = select(CampaignEnrollment).where(
        CampaignEnrollment.workspace_id == workspace_id,
        func.lower(CampaignEnrollment.recipient_email) == email.strip().lower(),
        CampaignEnrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.PAUSED]),
    )
    if campaign_id is not None:
        query = query.where(CampaignEnrollment.campaign_id == campaign_id)
    stopped = 0
    for enrollment in db.scalars(query).all():
        stop_enrollment(db, enrollment, status, reason)
        stopped += 1
    return stopped


def advance_sequences(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    """Draft follow-ups that are coming due, and complete finished enrollments/campaigns."""
    now = now or _now()
    created = stopped = 0
    with system_session(db):
        due = db.scalars(
            select(CampaignEnrollment)
            .join(Campaign, Campaign.id == CampaignEnrollment.campaign_id)
            .where(
                CampaignEnrollment.status == EnrollmentStatus.ACTIVE,
                CampaignEnrollment.next_step_number.is_not(None),
                CampaignEnrollment.current_step > 0,
                CampaignEnrollment.next_send_at <= now + DRAFT_LOOKAHEAD,
                Campaign.status == CampaignStatus.ACTIVE,
            )
            .limit(500),
        ).all()
        for enrollment in due:
            exists = db.scalar(
                select(EmailMessage.id).where(
                    EmailMessage.enrollment_id == enrollment.id,
                    EmailMessage.step_number == enrollment.next_step_number,
                ),
            )
            if exists:
                continue
            campaign = db.scalar(
                select(Campaign)
                .where(Campaign.id == enrollment.campaign_id)
                .options(selectinload(Campaign.steps)),
            )
            step = next(
                (s for s in campaign.steps if s.step_number == enrollment.next_step_number),
                None,
            )
            lead = db.scalar(
                select(Lead)
                .where(Lead.id == enrollment.lead_id)
                .options(selectinload(Lead.email_contacts), selectinload(Lead.company)),
            )
            if step is None or lead is None:
                stop_enrollment(db, enrollment, EnrollmentStatus.STOPPED, "Step or lead removed")
                stopped += 1
                continue
            workspace_settings = _workspace_settings(db, campaign.workspace_id)
            fallback = (
                workspace_settings.sender_name if workspace_settings else None
            ) or "The team"
            try:
                render_step_message(
                    db,
                    campaign=campaign,
                    step=step,
                    lead=lead,
                    enrollment=enrollment,
                    sender_fallback_name=fallback,
                    status=EmailMessageStatus.PENDING_APPROVAL,
                    scheduled_for=_aware(enrollment.next_send_at),
                )
                created += 1
            except StepRenderError as exc:
                stop_enrollment(
                    db, enrollment, EnrollmentStatus.STOPPED, f"No longer eligible: {exc}"
                )
                stopped += 1
        db.commit()
        completed = complete_finished(db, now=now)
    return {"created": created, "stopped": stopped, **completed}


def complete_finished(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    now = now or _now()
    enrollments = db.scalars(
        select(CampaignEnrollment).where(
            CampaignEnrollment.status == EnrollmentStatus.ACTIVE,
            CampaignEnrollment.next_step_number.is_(None),
            CampaignEnrollment.current_step > 0,
            CampaignEnrollment.last_sent_at <= now - COMPLETION_GRACE,
        ),
    ).all()
    for enrollment in enrollments:
        enrollment.status = EnrollmentStatus.COMPLETED
    db.flush()  # sessions don't autoflush; the counts below must see these changes

    campaigns_done = 0
    for campaign in db.scalars(
        select(Campaign).where(Campaign.status.in_([CampaignStatus.ACTIVE, CampaignStatus.PAUSED])),
    ).all():
        enrolled = db.scalar(
            select(func.count(CampaignEnrollment.id)).where(
                CampaignEnrollment.campaign_id == campaign.id,
            ),
        )
        if not enrolled:
            continue
        open_enrollments = db.scalar(
            select(func.count(CampaignEnrollment.id)).where(
                CampaignEnrollment.campaign_id == campaign.id,
                CampaignEnrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.PAUSED]),
            ),
        )
        open_messages = db.scalar(
            select(func.count(EmailMessage.id)).where(
                EmailMessage.campaign_id == campaign.id,
                EmailMessage.status.in_(ACTIVE_MESSAGE_STATES),
            ),
        )
        if not open_enrollments and not open_messages:
            campaign.status = CampaignStatus.COMPLETED
            campaign.completed_at = now
            campaigns_done += 1
    db.commit()
    return {"completed_enrollments": len(enrollments), "completed_campaigns": campaigns_done}
