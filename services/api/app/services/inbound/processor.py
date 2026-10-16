"""Apply inbound replies and delivery events to messages, leads, sequences and suppressions."""

from __future__ import annotations

import contextlib
import logging
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import metrics
from app.core.config import settings
from app.models.campaign import Campaign
from app.models.email_contact import EmailContact
from app.models.email_message import EmailMessage
from app.models.enrollment import CampaignEnrollment, EnrollmentStatus
from app.models.enums import (
    BounceStatus,
    CampaignStatus,
    EmailMessageStatus,
    LeadStatus,
    ReplyClassification,
    ReplyStatus,
)
from app.models.inbound import EmailEvent
from app.models.lead import Lead
from app.models.reply import Reply
from app.models.suppression import Suppression
from app.models.workspace import WorkspaceSettings
from app.services.campaigns.sequences import stop_enrollment, stop_enrollments_for_email
from app.services.compliance.opt_out import (
    cancel_pending_messages,
    process_unsubscribe_for_message,
    suppress_email,
)
from app.services.inbound import normalize
from app.services.inbound.normalize import DeliveryEvent, InboundEmail
from app.services.inbound.text import is_auto_reply, is_bounce_report, strip_quoted
from app.services.replies.classification import classify_reply
from app.services.replies.llm_classifier import RULE_CONFIDENCE_THRESHOLD, classify_with_llm
from app.services.sending.state import InvalidTransitionError, transition

logger = logging.getLogger(__name__)

SOFT_BOUNCE_LIMIT = 3
SAFETY_MIN_SENDS = 50
MAX_BOUNCE_RATE = 0.05
MAX_COMPLAINT_RATE = 0.001
_TOKEN_ADDRESS = re.compile(r"^(reply|unsubscribe)\+([A-Za-z0-9_\-]{8,128})@", re.IGNORECASE)

SENT_LIKE = (EmailMessageStatus.SENT, EmailMessageStatus.BOUNCED, EmailMessageStatus.COMPLAINED)


def _ai_labelling_on(db: Session, workspace_id: int) -> bool:
    if not settings.feature_ai_emails:
        return False
    mode = db.scalar(
        select(WorkspaceSettings.ai_mode).where(WorkspaceSettings.workspace_id == workspace_id),
    )
    return mode not in (None, "off")


# --- matching ---------------------------------------------------------------------------------


def _by_rfc_ids(db: Session, workspace_id: int, ids: list[str]) -> EmailMessage | None:
    if not ids:
        return None
    return db.scalar(
        select(EmailMessage)
        .where(EmailMessage.workspace_id == workspace_id, EmailMessage.rfc_message_id.in_(ids))
        .order_by(EmailMessage.sent_at.desc())
        .limit(1),
    )


def _by_correlation(
    db: Session, workspace_id: int, correlation_id: str | None
) -> EmailMessage | None:
    if not correlation_id or not correlation_id.isdigit():
        return None
    return db.scalar(
        select(EmailMessage).where(
            EmailMessage.id == int(correlation_id),
            EmailMessage.workspace_id == workspace_id,
        ),
    )


def _by_provider_id(db: Session, workspace_id: int, provider_id: str | None) -> EmailMessage | None:
    if not provider_id:
        return None
    return db.scalar(
        select(EmailMessage)
        .where(
            EmailMessage.workspace_id == workspace_id,
            (EmailMessage.provider_message_id == provider_id)
            | (EmailMessage.provider_message_id.like(f"{provider_id}.%"))
            | (EmailMessage.rfc_message_id == provider_id),
        )
        .limit(1),
    )


def _latest_to(db: Session, workspace_id: int, recipient: str | None) -> EmailMessage | None:
    if not recipient:
        return None
    return db.scalar(
        select(EmailMessage)
        .where(
            EmailMessage.workspace_id == workspace_id,
            func.lower(EmailMessage.recipient_email) == recipient.lower(),
            EmailMessage.status.in_(SENT_LIKE),
        )
        .order_by(EmailMessage.sent_at.desc())
        .limit(1),
    )


def _token_from(addresses: list[str], kind: str) -> str | None:
    for address in addresses:
        match = _TOKEN_ADDRESS.match(address)
        if match and match.group(1).lower() == kind:
            return match.group(2)
    return None


def match_inbound(
    db: Session, workspace_id: int, email: InboundEmail
) -> tuple[EmailMessage | None, str]:
    message = _by_rfc_ids(
        db, workspace_id, [i for i in [email.in_reply_to, *email.references] if i]
    )
    if message:
        return message, "in_reply_to"
    token = _token_from(email.to, "reply")
    if token:
        message = db.scalar(
            select(EmailMessage).where(
                EmailMessage.workspace_id == workspace_id,
                EmailMessage.reply_token == token,
            ),
        )
        if message:
            return message, "reply_token"
    message = _latest_to(db, workspace_id, email.from_email)
    if message:
        return message, "sender_fallback"
    return None, "unmatched"


def match_delivery(db: Session, workspace_id: int, event: DeliveryEvent) -> EmailMessage | None:
    return (
        _by_correlation(db, workspace_id, event.correlation_id)
        or _by_provider_id(db, workspace_id, event.provider_message_id)
        or _latest_to(db, workspace_id, event.recipient)
    )


# --- effects ----------------------------------------------------------------------------------


def _platform_suppress(db: Session, email: str, reason_code: str, message_id: int | None) -> None:
    normalized = email.strip().lower()
    exists = db.scalar(
        select(Suppression.id).where(
            Suppression.workspace_id.is_(None),
            Suppression.email == normalized,
        ),
    )
    if exists is None:
        db.add(
            Suppression(
                workspace_id=None,
                email=normalized,
                reason=reason_code.replace("_", " "),
                reason_code=reason_code,
                source="provider",
                email_message_id=message_id,
            ),
        )


def _safety_check(db: Session, campaign_id: int | None) -> None:
    """Pause a campaign automatically when bounces or complaints spike."""
    if campaign_id is None:
        return
    campaign = db.get(Campaign, campaign_id)
    if campaign is None or campaign.status != CampaignStatus.ACTIVE:
        return
    db.flush()
    counts = dict(
        db.execute(
            select(EmailMessage.status, func.count(EmailMessage.id))
            .where(EmailMessage.campaign_id == campaign_id, EmailMessage.status.in_(SENT_LIKE))
            .group_by(EmailMessage.status),
        ).all(),
    )
    total = sum(counts.values())
    if total < SAFETY_MIN_SENDS:
        return
    bounce_rate = counts.get(EmailMessageStatus.BOUNCED, 0) / total
    complaint_rate = counts.get(EmailMessageStatus.COMPLAINED, 0) / total
    if bounce_rate > MAX_BOUNCE_RATE or complaint_rate > MAX_COMPLAINT_RATE:
        campaign.status = CampaignStatus.PAUSED
        campaign.auto_paused_reason = (
            f"Paused automatically: bounce rate {bounce_rate:.1%}, "
            f"complaint rate {complaint_rate:.2%} over {total} sends"
        )
        logger.warning("Campaign %s auto-paused: %s", campaign_id, campaign.auto_paused_reason)


def _record_event(
    db: Session, workspace_id: int, message: EmailMessage | None, event: DeliveryEvent
) -> None:
    db.add(
        EmailEvent(
            workspace_id=workspace_id,
            email_message_id=message.id if message else None,
            recipient_email=(event.recipient or (message.recipient_email if message else None)),
            event_type=event.kind,
            provider=event.provider,
            reason=(event.reason or "")[:500] or None,
            occurred_at=event.occurred_at,
            data={"event_id": event.event_id},
        ),
    )


def process_delivery_event(db: Session, workspace_id: int, event: DeliveryEvent) -> str:
    message = match_delivery(db, workspace_id, event)
    recipient = (event.recipient or (message.recipient_email if message else "") or "").lower()
    _record_event(db, workspace_id, message, event)
    metrics.DELIVERY_EVENTS.labels(event.kind).inc()

    if event.kind == normalize.DELIVERED or not recipient:
        db.commit()
        return "recorded"

    if event.kind == normalize.BOUNCE_HARD:
        if message is not None:
            with contextlib.suppress(InvalidTransitionError):
                transition(db, message, EmailMessageStatus.BOUNCED, reason=event.reason)
            message.bounce_status = BounceStatus.HARD
        for contact in db.scalars(
            select(EmailContact).where(
                EmailContact.workspace_id == workspace_id,
                EmailContact.email == recipient,
            ),
        ).all():
            contact.is_verified = False
            contact.opted_out = True
        stop_enrollments_for_email(
            db,
            workspace_id=workspace_id,
            email=recipient,
            status=EnrollmentStatus.BOUNCED,
            reason="Hard bounce",
        )
        cancel_pending_messages(
            db, workspace_id=workspace_id, email=recipient, reason="hard bounce"
        )
        _platform_suppress(db, recipient, "hard_bounce", message.id if message else None)
        _safety_check(db, message.campaign_id if message else None)
        db.commit()
        return "hard_bounce"

    if event.kind == normalize.BOUNCE_SOFT:
        if message is not None and message.bounce_status == BounceStatus.NONE:
            message.bounce_status = BounceStatus.SOFT
        db.flush()
        soft_count = (
            db.scalar(
                select(func.count(EmailEvent.id)).where(
                    EmailEvent.workspace_id == workspace_id,
                    EmailEvent.recipient_email == recipient,
                    EmailEvent.event_type == normalize.BOUNCE_SOFT,
                ),
            )
            or 0
        )
        if soft_count >= SOFT_BOUNCE_LIMIT:
            suppress_email(
                db,
                workspace_id=workspace_id,
                email=recipient,
                reason="repeated soft bounces",
                source="provider",
                reason_code="soft_bounce",
                email_message_id=message.id if message else None,
            )
        db.commit()
        return "soft_bounce"

    if event.kind == normalize.COMPLAINT:
        if message is not None:
            with contextlib.suppress(InvalidTransitionError):
                transition(db, message, EmailMessageStatus.COMPLAINED, reason="spam complaint")
        suppress_email(
            db,
            workspace_id=workspace_id,
            email=recipient,
            reason="spam complaint",
            source="provider",
            lead_id=message.lead_id if message else None,
            reason_code="complaint",
            email_message_id=message.id if message else None,
        )
        _platform_suppress(db, recipient, "complaint", message.id if message else None)
        _safety_check(db, message.campaign_id if message else None)
        db.commit()
        return "complaint"

    if event.kind == normalize.UNSUBSCRIBE:
        suppress_email(
            db,
            workspace_id=workspace_id,
            email=recipient,
            reason="unsubscribe",
            source="provider",
            lead_id=message.lead_id if message else None,
            reason_code="unsubscribe",
            email_message_id=message.id if message else None,
        )
        db.commit()
        return "unsubscribe"

    db.commit()
    return "ignored"


def process_inbound_email(db: Session, workspace_id: int, email: InboundEmail) -> Reply | None:
    """Store a reply, classify it and apply its effects. Returns None for non-replies."""
    # 1. Unsubscribe by mailto (List-Unsubscribe: <mailto:unsubscribe+TOKEN@...>).
    unsubscribe_token = _token_from(email.to, "unsubscribe")
    if unsubscribe_token:
        process_unsubscribe_for_message(db, unsubscribe_token)
        return None

    # 2. Bounce reports arriving as email (common with SMTP + IMAP).
    if is_bounce_report(email.from_email, email.subject, email.content_type):
        message, _ = match_inbound(db, workspace_id, email)
        for recipient in email.failed_recipients or ([message.recipient_email] if message else []):
            process_delivery_event(
                db,
                workspace_id,
                DeliveryEvent(
                    kind=normalize.BOUNCE_HARD,
                    provider="mailbox",
                    event_id=email.message_id or f"dsn:{recipient}",
                    recipient=recipient,
                    provider_message_id=message.rfc_message_id if message else None,
                    correlation_id=str(message.id) if message else None,
                    reason=email.subject,
                ),
            )
        return None

    # 3. Duplicate delivery of the same reply (webhook retries, IMAP re-reads).
    if email.message_id:
        duplicate = db.scalar(
            select(Reply).where(
                Reply.workspace_id == workspace_id,
                Reply.message_id_header == email.message_id,
            ),
        )
        if duplicate is not None:
            return duplicate

    message, method = match_inbound(db, workspace_id, email)
    auto = is_auto_reply(email.headers, email.subject)
    stripped = strip_quoted(email.text)
    classification, confidence = classify_reply(stripped, email.subject, is_auto_reply=auto)
    classified_by = "rule"
    if confidence < RULE_CONFIDENCE_THRESHOLD and not auto and _ai_labelling_on(db, workspace_id):
        llm_result = classify_with_llm(db, workspace_id, stripped, email.subject)
        if llm_result is not None:
            classification, confidence = llm_result
            classified_by = "llm"

    lead = db.get(Lead, message.lead_id) if message else None
    reply = Reply(
        workspace_id=workspace_id,
        email_message_id=message.id if message else None,
        lead_id=lead.id if lead else None,
        enrollment_id=message.enrollment_id if message else None,
        from_email=email.from_email,
        subject=(email.subject or "")[:500] or None,
        body=stripped[:20000],
        raw_body=email.text[:100_000],
        message_id_header=email.message_id,
        in_reply_to=email.in_reply_to,
        classification=classification,
        classified_by=classified_by,
        classification_confidence=confidence,
        match_method=method,
        is_auto_reply=auto
        or classification
        in {
            ReplyClassification.OUT_OF_OFFICE,
            ReplyClassification.AUTO_REPLY,
        },
        received_at=email.received_at,
    )
    db.add(reply)
    db.flush()
    apply_reply_effects(db, reply, message, lead)
    db.commit()
    metrics.REPLIES_RECEIVED.labels(str(classification)).inc()
    return reply


def apply_reply_effects(
    db: Session,
    reply: Reply,
    message: EmailMessage | None,
    lead: Lead | None,
) -> None:
    classification = ReplyClassification(str(reply.classification))
    if message is not None:
        message.reply_status = ReplyStatus.RECEIVED

    if classification == ReplyClassification.UNSUBSCRIBE:
        suppress_email(
            db,
            workspace_id=reply.workspace_id,
            email=reply.from_email,
            reason="asked to stop in a reply",
            source="reply",
            lead_id=lead.id if lead else None,
            reason_code="reply_opt_out",
            email_message_id=message.id if message else None,
        )
        return

    if classification in {ReplyClassification.OUT_OF_OFFICE, ReplyClassification.AUTO_REPLY}:
        return  # the sequence carries on

    enrollment = db.get(CampaignEnrollment, reply.enrollment_id) if reply.enrollment_id else None
    campaign = db.get(Campaign, enrollment.campaign_id) if enrollment else None
    if enrollment is not None and (campaign is None or campaign.stop_on_reply):
        status = (
            EnrollmentStatus.STOPPED
            if classification == ReplyClassification.WRONG_PERSON
            else EnrollmentStatus.REPLIED
        )
        stop_enrollment(db, enrollment, status, f"Reply received ({classification})")

    if lead is not None and lead.status not in {
        LeadStatus.MEETING_BOOKED,
        LeadStatus.CLIENT,
        LeadStatus.OPTED_OUT,
    }:
        lead.status = LeadStatus.REPLIED


def link_reply(db: Session, reply: Reply, message: EmailMessage) -> Reply:
    """Attach an unmatched reply to a sent email by hand, then apply the usual effects."""
    reply.email_message_id = message.id
    reply.enrollment_id = message.enrollment_id
    reply.lead_id = message.lead_id
    reply.match_method = "manual"
    apply_reply_effects(db, reply, message, db.get(Lead, message.lead_id))
    db.commit()
    db.refresh(reply)
    return reply
