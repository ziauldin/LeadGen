"""Delivery pipeline: dispatch (claim due messages) -> deliver (send exactly once) -> reap.

Guarantees:
* A message is sent at most once: delivery starts with a conditional UPDATE from ``queued`` to
  ``sending``; a second worker (or a retried task) finds nothing to claim.
* Hitting a limit or the sending window defers a message (it stays ``approved`` with
  ``next_attempt_at``); it never fails because of timing.
* Provider rate limits / outages retry with backoff; permanent rejections fail immediately.
* A message stuck in ``sending`` (worker died mid-send) is failed for review, never re-sent
  automatically, because we cannot know whether the provider accepted it.
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.tenancy import system_session
from app.models.audit_log import AuditLog
from app.models.campaign import Campaign
from app.models.email_message import EmailMessage
from app.models.enums import CampaignStatus, EmailMessageStatus, LeadStatus
from app.models.lead import Lead
from app.models.workspace import Workspace, WorkspaceSettings
from app.services.billing.usage import record_usage
from app.services.sending.base import SendKind
from app.services.sending.gate import GateKind, campaign_sent_today, evaluate_send_gate
from app.services.sending.mime import build_outbound, make_message_id
from app.services.sending.provider_factory import resolve_sender
from app.services.sending.schedule import schedule_for
from app.services.sending.state import transition

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
QUEUED_TIMEOUT = timedelta(minutes=15)
SENDING_TIMEOUT = timedelta(minutes=10)
DISPATCH_BATCH_MAX = 200


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _retry_delay(attempts: int) -> timedelta:
    return timedelta(minutes=min(60, 2**attempts))


def _workspace_settings(db: Session, workspace_id: int) -> WorkspaceSettings | None:
    return db.scalar(
        select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == workspace_id)
    )


def _ensure_identifiers(message: EmailMessage, from_email: str) -> None:
    if not message.rfc_message_id:
        message.rfc_message_id = make_message_id(from_email)
    if not message.reply_token:
        message.reply_token = secrets.token_urlsafe(18)
    if not message.idempotency_key:
        message.idempotency_key = f"lg-{message.workspace_id}-{message.id}-{secrets.token_hex(6)}"
    if not message.recipient_domain and "@" in message.recipient_email:
        message.recipient_domain = message.recipient_email.rsplit("@", 1)[-1].lower()


def _previous_message_id(db: Session, message: EmailMessage) -> str | None:
    """RFC Message-ID of the latest earlier email to the same lead in this campaign (threading)."""
    if message.campaign_id is None:
        return None
    return db.scalar(
        select(EmailMessage.rfc_message_id)
        .where(
            EmailMessage.campaign_id == message.campaign_id,
            EmailMessage.lead_id == message.lead_id,
            EmailMessage.id != message.id,
            EmailMessage.status.in_([EmailMessageStatus.SENT]),
            EmailMessage.rfc_message_id.is_not(None),
        )
        .order_by(EmailMessage.sent_at.desc())
        .limit(1),
    )


def deliver_message(db: Session, message_id: int, *, now: datetime | None = None) -> str:
    """Send one queued message. Returns sent / deferred / cancelled / retry / failed / skipped."""
    now = now or _now()
    claimed = db.execute(
        update(EmailMessage)
        .where(EmailMessage.id == message_id, EmailMessage.status == EmailMessageStatus.QUEUED)
        .values(
            status=EmailMessageStatus.SENDING,
            sending_started_at=now,
            send_attempts=EmailMessage.send_attempts + 1,
        )
        .execution_options(synchronize_session=False),
    )
    db.commit()
    if not claimed.rowcount:  # type: ignore[attr-defined]
        return "skipped"  # already handled by another worker / attempt

    message = db.scalar(
        select(EmailMessage)
        .where(EmailMessage.id == message_id)
        .options(
            selectinload(EmailMessage.lead).selectinload(Lead.email_contacts),
            selectinload(EmailMessage.campaign),
        )
        .execution_options(populate_existing=True),
    )
    if message is None or message.campaign is None or message.lead is None:
        if message is not None:
            transition(db, message, EmailMessageStatus.CANCELLED, reason="missing campaign or lead")
            message.failure_reason = "Missing campaign or lead"
            db.commit()
        return "cancelled"

    campaign, lead = message.campaign, message.lead
    workspace = db.get(Workspace, message.workspace_id)
    ws_settings = _workspace_settings(db, message.workspace_id)
    sender, credential = resolve_sender(db, message.workspace_id, campaign.sender_credential_id)

    decision = evaluate_send_gate(
        db,
        campaign,
        message,
        lead,
        now,
        workspace=workspace,
        workspace_settings=ws_settings,
        credential=credential,
    )
    if decision.kind == GateKind.BLOCK:
        transition(db, message, EmailMessageStatus.CANCELLED, reason="; ".join(decision.reasons))
        message.failure_reason = "; ".join(decision.reasons)[:255]
        db.commit()
        return "cancelled"
    if decision.kind == GateKind.DEFER:
        transition(db, message, EmailMessageStatus.APPROVED, audit=False)
        message.send_attempts = max(0, message.send_attempts - 1)  # not a real attempt
        message.next_attempt_at = decision.retry_at
        message.last_error = "; ".join(decision.reasons)
        db.commit()
        return "deferred"

    _ensure_identifiers(message, sender.from_email)
    message.sender_credential_id = credential.id if credential else None
    db.commit()  # persist identifiers before the provider call (needed to match webhooks)

    outbound = build_outbound(
        message,
        from_email=sender.from_email,
        workspace_settings=ws_settings,
        in_reply_to=_previous_message_id(db, message),
    )
    result = sender.send(outbound)

    if result.kind == SendKind.OK:
        transition(db, message, EmailMessageStatus.SENT, reason=sender.provider_name, audit=False)
        message.sent_at = _now()
        message.provider_message_id = result.provider_message_id
        message.last_error = None
        message.next_attempt_at = None
        record_usage(db, message.workspace_id, "monthly_sends")
        if lead.status not in {LeadStatus.REPLIED, LeadStatus.MEETING_BOOKED, LeadStatus.CLIENT}:
            lead.status = LeadStatus.CONTACTED
        db.add(
            AuditLog(
                workspace_id=message.workspace_id,
                action="email_sent",
                entity_type="email_message",
                entity_id=message.id,
                metadata_={
                    "provider": sender.provider_name,
                    "provider_message_id": result.provider_message_id,
                },
            ),
        )
        db.commit()
        return "sent"

    message.last_error = (result.error or "Send failed")[:2000]
    if result.kind == SendKind.TRANSIENT and message.send_attempts < MAX_ATTEMPTS:
        transition(db, message, EmailMessageStatus.APPROVED, audit=False)
        message.next_attempt_at = _now() + _retry_delay(message.send_attempts)
        db.commit()
        return "retry"

    transition(db, message, EmailMessageStatus.FAILED, reason=result.error)
    message.failure_reason = (
        "Provider rejected the email"
        if result.kind == SendKind.PERMANENT
        else f"Gave up after {message.send_attempts} attempts"
    )
    db.commit()
    return "failed"


def _due_messages_query(campaign_id: int, now: datetime, limit: int):
    return (
        select(EmailMessage.id)
        .where(
            EmailMessage.campaign_id == campaign_id,
            EmailMessage.status == EmailMessageStatus.APPROVED,
            (EmailMessage.next_attempt_at.is_(None)) | (EmailMessage.next_attempt_at <= now),
            (EmailMessage.scheduled_for.is_(None)) | (EmailMessage.scheduled_for <= now),
        )
        .order_by(EmailMessage.scheduled_for.asc().nulls_first(), EmailMessage.id.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )


def _claim_for_campaign(db: Session, campaign: Campaign, now: datetime) -> list[int]:
    workspace = db.get(Workspace, campaign.workspace_id)
    if workspace is None or workspace.sending_suspended_at is not None:
        return []
    schedule = schedule_for(campaign, workspace, _workspace_settings(db, campaign.workspace_id))
    if not schedule.is_open(now):
        return []
    in_flight = (
        db.scalar(
            select(func.count(EmailMessage.id)).where(
                EmailMessage.campaign_id == campaign.id,
                EmailMessage.status.in_([EmailMessageStatus.QUEUED, EmailMessageStatus.SENDING]),
            ),
        )
        or 0
    )
    capacity = (
        campaign.daily_send_limit - campaign_sent_today(db, campaign, schedule, now) - in_flight
    )
    if capacity <= 0:
        return []
    ids = list(db.scalars(_due_messages_query(campaign.id, now, min(capacity, DISPATCH_BATCH_MAX))))
    if ids:
        db.execute(
            update(EmailMessage)
            .where(EmailMessage.id.in_(ids), EmailMessage.status == EmailMessageStatus.APPROVED)
            .values(status=EmailMessageStatus.QUEUED, queued_at=now)
            .execution_options(synchronize_session=False),
        )
    db.commit()
    return ids


def dispatch(
    db: Session,
    *,
    now: datetime | None = None,
    workspace_id: int | None = None,
    campaign_id: int | None = None,
    enqueue: Callable[[int], None] | None = None,
) -> dict[str, int]:
    """Claim due messages for active campaigns and deliver them.

    With ``enqueue`` (the beat job) each claimed message becomes a Celery task. Without it
    (an admin pressing "send now") messages are delivered inline and counted.
    """
    now = now or _now()
    counts = {"sent": 0, "failed": 0, "skipped": 0, "queued": 0}

    query = select(Campaign).where(Campaign.status == CampaignStatus.ACTIVE)
    if workspace_id is not None:
        query = query.where(Campaign.workspace_id == workspace_id)
    if campaign_id is not None:
        query = query.where(Campaign.id == campaign_id)

    def run() -> None:
        for campaign in list(db.scalars(query).all()):
            for message_id in _claim_for_campaign(db, campaign, now):
                if enqueue is not None:
                    try:
                        enqueue(message_id)
                        counts["queued"] += 1
                    except Exception:
                        logger.exception("Could not enqueue message %s; returning it", message_id)
                        db.execute(
                            update(EmailMessage)
                            .where(EmailMessage.id == message_id)
                            .values(status=EmailMessageStatus.APPROVED)
                            .execution_options(synchronize_session=False),
                        )
                        db.commit()
                    continue
                outcome = deliver_message(db, message_id, now=now)
                if outcome == "sent":
                    counts["sent"] += 1
                elif outcome == "failed":
                    counts["failed"] += 1
                else:
                    counts["skipped"] += 1

    if workspace_id is None:
        with system_session(db):
            run()
    else:
        run()
    return counts


def reap_stuck_messages(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    now = now or _now()
    with system_session(db):
        requeued = db.execute(
            update(EmailMessage)
            .where(
                EmailMessage.status == EmailMessageStatus.QUEUED,
                EmailMessage.queued_at < now - QUEUED_TIMEOUT,
            )
            .values(status=EmailMessageStatus.APPROVED)
            .execution_options(synchronize_session=False),
        ).rowcount  # type: ignore[attr-defined]
        failed = db.execute(
            update(EmailMessage)
            .where(
                EmailMessage.status == EmailMessageStatus.SENDING,
                EmailMessage.sending_started_at < now - SENDING_TIMEOUT,
            )
            .values(
                status=EmailMessageStatus.FAILED,
                failure_reason="Unknown outcome (worker stopped mid-send). Review before resending.",
            )
            .execution_options(synchronize_session=False),
        ).rowcount  # type: ignore[attr-defined]
        db.commit()
    if requeued or failed:
        logger.warning("Reaper: %s re-queued, %s failed for review", requeued, failed)
    return {"requeued": requeued or 0, "failed": failed or 0}


# Backwards-compatible name used by the API's "send now" action.
def process_active_campaigns(
    db: Session,
    actor_id: int | None = None,
    *,
    workspace_id: int | None = None,
    campaign_id: int | None = None,
) -> dict[str, int]:
    counts = dispatch(db, workspace_id=workspace_id, campaign_id=campaign_id)
    return {"sent": counts["sent"], "failed": counts["failed"], "skipped": counts["skipped"]}
