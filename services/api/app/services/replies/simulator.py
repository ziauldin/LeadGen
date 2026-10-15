"""Development-only reply simulator for workspaces using the mock email provider.

Fake replies go through the real inbound pipeline (matching, classification, sequence stop),
so local testing exercises the same code paths as provider webhooks and IMAP.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus
from app.services.inbound.normalize import InboundEmail
from app.services.inbound.processor import process_inbound_email

MOCK_REPLIES = [
    "Thanks for reaching out, happy to chat next week if you have 15 minutes.",
    "Not relevant for us right now, please do not contact again.",
    "Could you share a bit more about how this differs from what we use today?",
]


def sync_mock_replies(db: Session, workspace_id: int) -> int:
    sent_messages = db.scalars(
        select(EmailMessage)
        .where(
            EmailMessage.workspace_id == workspace_id,
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
        process_inbound_email(
            db,
            workspace_id,
            InboundEmail(
                from_email=message.recipient_email,
                to=["mock-inbox@leadsgen.local"],
                subject=f"Re: {message.subject}",
                text=MOCK_REPLIES[index % len(MOCK_REPLIES)],
                message_id=f"mock-reply-{message.id}@leadsgen.local",
                in_reply_to=message.rfc_message_id,
                received_at=now - timedelta(hours=index + 1),
            ),
        )
        synced += 1
    return synced
