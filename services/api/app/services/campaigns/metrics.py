"""Campaign numbers for the overview tab: funnel, rates and a per-step breakdown."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.email_message import EmailMessage
from app.models.enrollment import CampaignEnrollment
from app.models.enums import EmailMessageStatus as S
from app.models.enums import ReplyClassification as C
from app.models.reply import Reply

SENT_STATES = (S.SENT, S.BOUNCED, S.COMPLAINED)
HUMAN_REPLIES = (C.POSITIVE, C.NEUTRAL, C.OBJECTION, C.UNSUBSCRIBE, C.WRONG_PERSON, C.UNKNOWN)


def _rate(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0


def campaign_metrics(db: Session, campaign: Campaign) -> dict:
    messages_by_status = {
        str(status): count
        for status, count in db.execute(
            select(EmailMessage.status, func.count(EmailMessage.id))
            .where(EmailMessage.campaign_id == campaign.id)
            .group_by(EmailMessage.status),
        ).all()
    }
    enrollments_by_status = {
        str(status): count
        for status, count in db.execute(
            select(CampaignEnrollment.status, func.count(CampaignEnrollment.id))
            .where(CampaignEnrollment.campaign_id == campaign.id)
            .group_by(CampaignEnrollment.status),
        ).all()
    }
    replies_by_class = {
        str(classification): count
        for classification, count in db.execute(
            select(Reply.classification, func.count(Reply.id))
            .join(EmailMessage, EmailMessage.id == Reply.email_message_id)
            .where(EmailMessage.campaign_id == campaign.id)
            .group_by(Reply.classification),
        ).all()
    }

    sent = sum(messages_by_status.get(str(s), 0) for s in SENT_STATES)
    bounced = messages_by_status.get(str(S.BOUNCED), 0)
    complained = messages_by_status.get(str(S.COMPLAINED), 0)
    human_replies = sum(replies_by_class.get(str(c), 0) for c in HUMAN_REPLIES)
    positive = replies_by_class.get(str(C.POSITIVE), 0)

    step_rows = db.execute(
        select(EmailMessage.step_number, EmailMessage.status, func.count(EmailMessage.id))
        .where(EmailMessage.campaign_id == campaign.id)
        .group_by(EmailMessage.step_number, EmailMessage.status),
    ).all()
    step_replies = dict(
        db.execute(
            select(EmailMessage.step_number, func.count(Reply.id))
            .join(EmailMessage, EmailMessage.id == Reply.email_message_id)
            .where(
                EmailMessage.campaign_id == campaign.id,
                Reply.classification.in_([str(c) for c in HUMAN_REPLIES]),
            )
            .group_by(EmailMessage.step_number),
        ).all(),
    )
    steps: dict[int, dict[str, int]] = {}
    for step in sorted(campaign.steps, key=lambda s: s.step_number):
        steps[step.step_number] = {"drafts": 0, "awaiting_approval": 0, "sent": 0, "bounced": 0}
    for step_number, status, count in step_rows:
        entry = steps.setdefault(
            step_number or 1,
            {"drafts": 0, "awaiting_approval": 0, "sent": 0, "bounced": 0},
        )
        entry["drafts"] += count
        if status in (S.DRAFT, S.PENDING_APPROVAL):
            entry["awaiting_approval"] += count
        if status in SENT_STATES:
            entry["sent"] += count
        if status == S.BOUNCED:
            entry["bounced"] += count

    return {
        "campaign_id": campaign.id,
        "status": str(campaign.status),
        "enrolled": sum(enrollments_by_status.values()),
        "enrollments_by_status": enrollments_by_status,
        "messages_by_status": messages_by_status,
        "awaiting_approval": messages_by_status.get(str(S.DRAFT), 0)
        + messages_by_status.get(str(S.PENDING_APPROVAL), 0),
        "scheduled": messages_by_status.get(str(S.APPROVED), 0)
        + messages_by_status.get(str(S.QUEUED), 0),
        "sent": sent,
        "bounced": bounced,
        "complained": complained,
        "replies": human_replies,
        "positive_replies": positive,
        "replies_by_classification": replies_by_class,
        "reply_rate": _rate(human_replies, sent),
        "positive_rate": _rate(positive, sent),
        "bounce_rate": _rate(bounced, sent),
        "complaint_rate": _rate(complained, sent),
        "steps": [
            {
                "step_number": number,
                **values,
                "replies": step_replies.get(number, 0),
                "reply_rate": _rate(step_replies.get(number, 0), values["sent"]),
            }
            for number, values in sorted(steps.items())
        ],
    }
