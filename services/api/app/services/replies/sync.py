from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus, LeadStatus, ReplyClassification, ReplyStatus
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.reply import Reply
from app.services.compliance.opt_out import process_unsubscribe_for_message
from app.services.replies.classification import classify_reply_body


MOCK_REPLIES = [
    (
        "Thanks for reaching out — happy to chat next week if you have 15 minutes.",
        ReplyClassification.POSITIVE,
    ),
    (
        "Not relevant for us right now, please do not contact again.",
        ReplyClassification.UNSUBSCRIBE,
    ),
    (
        "Could you share a bit more about how this differs from a wellbeing dashboard?",
        ReplyClassification.NEUTRAL,
    ),
]


def sync_mock_replies(db: Session, user_id: int) -> int:
    sent_messages = db.scalars(
        select(EmailMessage)
        .join(Lead, EmailMessage.lead_id == Lead.id)
        .join(Niche, Lead.niche_id == Niche.id)
        .where(
            Niche.user_id == user_id,
            EmailMessage.status == EmailMessageStatus.SENT,
        )
        .options(selectinload(EmailMessage.replies))
        .order_by(EmailMessage.sent_at.desc())
        .limit(10),
    ).all()

    synced = 0
    now = datetime.now(UTC)

    for index, message in enumerate(sent_messages):
        if message.replies:
            continue

        body, expected_class = MOCK_REPLIES[index % len(MOCK_REPLIES)]
        classification = classify_reply_body(body)
        if classification == ReplyClassification.UNKNOWN:
            classification = expected_class

        reply = Reply(
            email_message_id=message.id,
            from_email=message.recipient_email,
            body=body,
            classification=classification,
            received_at=now - timedelta(hours=index + 1),
        )
        db.add(reply)

        message.reply_status = ReplyStatus.RECEIVED
        lead = message.lead
        if lead:
            if classification == ReplyClassification.POSITIVE:
                lead.status = LeadStatus.REPLIED
            elif classification == ReplyClassification.UNSUBSCRIBE:
                lead.status = LeadStatus.OPTED_OUT
                lead.score = 0.0
                if message.unsubscribe_token:
                    process_unsubscribe_for_message(db, message.unsubscribe_token)

        synced += 1

    db.commit()
    return synced


def update_reply(
    db: Session,
    reply_id: int,
    user_id: int,
    classification: ReplyClassification | None = None,
    mark_meeting_booked: bool = False,
    notes: str | None = None,
) -> Reply:
    reply = db.scalar(
        select(Reply)
        .join(EmailMessage, Reply.email_message_id == EmailMessage.id)
        .join(Lead, EmailMessage.lead_id == Lead.id)
        .join(Niche, Lead.niche_id == Niche.id)
        .where(Reply.id == reply_id, Niche.user_id == user_id)
        .options(selectinload(Reply.email_message).selectinload(EmailMessage.lead)),
    )
    if reply is None:
        raise ValueError("Reply not found")

    if classification is not None:
        reply.classification = classification
    if notes is not None:
        reply.notes = notes

    lead = reply.email_message.lead if reply.email_message else None
    if mark_meeting_booked and lead:
        lead.status = LeadStatus.MEETING_BOOKED
    elif classification == ReplyClassification.POSITIVE and lead:
        lead.status = LeadStatus.REPLIED

    db.commit()
    db.refresh(reply)
    return reply
