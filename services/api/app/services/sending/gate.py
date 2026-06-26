from dataclasses import dataclass
from datetime import UTC, datetime, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.campaign import Campaign
from app.models.email_message import EmailMessage
from app.models.enums import CampaignStatus, EmailMessageStatus
from app.models.lead import Lead
from app.services.compliance.outreach import validate_lead_for_outreach


@dataclass
class SendGateResult:
    allowed: bool
    reasons: list[str]


def _parse_hhmm(value: str | None) -> time | None:
    if not value:
        return None
    hour, minute = value.split(":")
    return time(hour=int(hour), minute=int(minute))


def _within_sending_window(campaign: Campaign, now: datetime) -> bool:
    start = _parse_hhmm(campaign.sending_window_start or settings.default_sending_window_start)
    end = _parse_hhmm(campaign.sending_window_end or settings.default_sending_window_end)
    current = now.time()
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def _start_of_day(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _count_campaign_sends_today(db: Session, campaign_id: int, now: datetime) -> int:
    day_start = _start_of_day(now)
    return (
        db.scalar(
            select(func.count(EmailMessage.id)).where(
                EmailMessage.campaign_id == campaign_id,
                EmailMessage.status == EmailMessageStatus.SENT,
                EmailMessage.sent_at >= day_start,
            ),
        )
        or 0
    )


def _count_domain_sends_today(db: Session, campaign_id: int, domain: str, now: datetime) -> int:
    day_start = _start_of_day(now)
    pattern = f"%@{domain.lower()}"
    return (
        db.scalar(
            select(func.count(EmailMessage.id)).where(
                EmailMessage.campaign_id == campaign_id,
                EmailMessage.status == EmailMessageStatus.SENT,
                EmailMessage.sent_at >= day_start,
                EmailMessage.recipient_email.ilike(pattern),
            ),
        )
        or 0
    )


def evaluate_send_gate(
    db: Session,
    campaign: Campaign,
    message: EmailMessage,
    lead: Lead,
    now: datetime | None = None,
) -> SendGateResult:
    reasons: list[str] = []
    now = now or datetime.now(UTC)

    if campaign.status != CampaignStatus.ACTIVE:
        reasons.append("Campaign is not active")

    if message.status != EmailMessageStatus.APPROVED:
        reasons.append("Email message is not approved")

    if not message.recipient_email:
        reasons.append("Recipient email is missing")

    reasons.extend(validate_lead_for_outreach(lead, db))

    if not _within_sending_window(campaign, now):
        reasons.append("Current time is outside the configured sending window")

    daily_limit = campaign.daily_send_limit or settings.default_daily_send_limit
    if _count_campaign_sends_today(db, campaign.id, now) >= daily_limit:
        reasons.append("Campaign daily send limit reached")

    if message.recipient_email and "@" in message.recipient_email:
        domain = message.recipient_email.split("@", 1)[1].lower()
        if _count_domain_sends_today(db, campaign.id, domain, now) >= settings.default_per_domain_limit:
            reasons.append(f"Per-domain daily limit reached for {domain}")

    return SendGateResult(allowed=not reasons, reasons=reasons)
