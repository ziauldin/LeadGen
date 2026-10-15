"""The send gate: the last check before an email leaves.

Decisions are ALLOW, DEFER (temporary: try again later, the message stays approved) or BLOCK
(permanent: the message is cancelled with the reason). Hitting a limit or being outside the
sending window must never fail a message.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.campaign import Campaign
from app.models.email_message import EmailMessage
from app.models.enrollment import CampaignEnrollment, EnrollmentStatus
from app.models.enums import CampaignStatus, EmailMessageStatus, LeadStatus
from app.models.lead import Lead
from app.models.provider_credential import ProviderCredential
from app.models.workspace import Workspace, WorkspaceSettings
from app.services.billing.plans import limits_for
from app.services.billing.usage import current_usage
from app.services.compliance.outreach import validate_lead_for_outreach
from app.services.sending.schedule import SendingSchedule, schedule_for
from app.services.sending.warmup import daily_cap

SENT_STATES = (EmailMessageStatus.SENT, EmailMessageStatus.BOUNCED, EmailMessageStatus.COMPLAINED)


class GateKind(StrEnum):
    ALLOW = "allow"
    DEFER = "defer"
    BLOCK = "block"


@dataclass
class GateDecision:
    kind: GateKind
    reasons: list[str] = field(default_factory=list)
    retry_at: datetime | None = None

    @property
    def allowed(self) -> bool:
        return self.kind == GateKind.ALLOW


def _sent_since(db: Session, *conditions: object) -> int:
    return (
        db.scalar(
            select(func.count(EmailMessage.id)).where(
                EmailMessage.status.in_(SENT_STATES),
                *conditions,  # type: ignore[arg-type]
            ),
        )
        or 0
    )


def campaign_sent_today(
    db: Session, campaign: Campaign, schedule: SendingSchedule, now: datetime
) -> int:
    day_start, day_end = schedule.day_bounds_utc(now)
    return _sent_since(
        db,
        EmailMessage.campaign_id == campaign.id,
        EmailMessage.sent_at >= day_start,
        EmailMessage.sent_at < day_end,
    )


def _domain_sent_today(
    db: Session,
    workspace_id: int,
    domain: str,
    schedule: SendingSchedule,
    now: datetime,
) -> int:
    day_start, day_end = schedule.day_bounds_utc(now)
    return _sent_since(
        db,
        EmailMessage.workspace_id == workspace_id,
        EmailMessage.recipient_domain == domain,
        EmailMessage.sent_at >= day_start,
        EmailMessage.sent_at < day_end,
    )


def credential_sent_today(db: Session, credential: ProviderCredential, now: datetime) -> int:
    day_start = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return _sent_since(
        db,
        EmailMessage.sender_credential_id == credential.id,
        EmailMessage.sent_at >= day_start,
    )


def _next_month(now: datetime) -> datetime:
    first = now.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (first + timedelta(days=32)).replace(day=1)


def evaluate_send_gate(
    db: Session,
    campaign: Campaign,
    message: EmailMessage,
    lead: Lead,
    now: datetime | None = None,
    *,
    workspace: Workspace | None = None,
    workspace_settings: WorkspaceSettings | None = None,
    credential: ProviderCredential | None = None,
) -> GateDecision:
    now = now or datetime.now(UTC)
    workspace = workspace or db.get(Workspace, message.workspace_id)

    # --- permanent reasons: the message must not be sent at all ---------------------------
    blocks: list[str] = []
    if str(message.status) not in {
        EmailMessageStatus.APPROVED,
        EmailMessageStatus.QUEUED,
        EmailMessageStatus.SENDING,
    }:
        blocks.append("Email message is not approved")
    if not message.recipient_email:
        blocks.append("Recipient email is missing")
    if lead.status in {LeadStatus.OPTED_OUT, LeadStatus.DISQUALIFIED}:
        blocks.append(f"Lead is {lead.status}")
    blocks.extend(validate_lead_for_outreach(lead, db))
    if message.enrollment_id is not None:
        enrollment = db.get(CampaignEnrollment, message.enrollment_id)
        if enrollment is not None and enrollment.status != EnrollmentStatus.ACTIVE:
            blocks.append(f"Sequence for this lead is {enrollment.status}")
    if blocks:
        return GateDecision(GateKind.BLOCK, blocks)

    # --- temporary reasons: keep the message and try again later --------------------------
    if campaign.status != CampaignStatus.ACTIVE:
        return GateDecision(GateKind.DEFER, [f"Campaign is not active ({campaign.status})"])
    if workspace is not None and workspace.sending_suspended_at is not None:
        return GateDecision(
            GateKind.DEFER,
            ["Sending is suspended for this workspace"],
            now + timedelta(hours=1),
        )

    schedule = schedule_for(campaign, workspace, workspace_settings)
    if not schedule.is_open(now):
        return GateDecision(
            GateKind.DEFER,
            ["Current time is outside the configured sending window"],
            schedule.next_open(now),
        )

    daily_limit = campaign.daily_send_limit or settings.default_daily_send_limit
    if campaign_sent_today(db, campaign, schedule, now) >= daily_limit:
        return GateDecision(
            GateKind.DEFER,
            ["Campaign daily send limit reached"],
            schedule.next_day_open(now),
        )

    domain = (message.recipient_domain or message.recipient_email.rsplit("@", 1)[-1]).lower()
    per_domain = campaign.per_domain_limit or settings.default_per_domain_limit
    if _domain_sent_today(db, message.workspace_id, domain, schedule, now) >= per_domain:
        return GateDecision(
            GateKind.DEFER,
            [f"Per-domain daily limit reached for {domain}"],
            schedule.next_day_open(now),
        )

    cap = daily_cap(credential, now.astimezone(UTC).date())
    if (
        credential is not None
        and cap is not None
        and credential_sent_today(db, credential, now) >= cap
    ):
        return GateDecision(
            GateKind.DEFER,
            ["Warm-up daily cap reached for this sending account"],
            schedule.next_day_open(now),
        )

    if workspace is not None:
        limit = limits_for(workspace).monthly_sends
        if current_usage(db, workspace.id, "monthly_sends", now=now) >= limit:
            return GateDecision(
                GateKind.DEFER,
                ["Monthly send limit for your plan reached"],
                _next_month(now),
            )

    return GateDecision(GateKind.ALLOW)
