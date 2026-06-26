from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.campaign import Campaign
from app.models.email_message import EmailMessage
from app.models.enums import CampaignStatus, EmailMessageStatus, LeadStatus, ReplyClassification
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.reply import Reply
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardSummary(BaseModel):
    total_leads: int
    qualified_leads: int
    contacted_leads: int
    replied_leads: int
    active_campaigns: int
    pending_replies: int
    positive_replies: int
    lead_status_counts: dict[str, int]


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    niche_ids = db.scalars(select(Niche.id).where(Niche.user_id == current_user.id)).all()
    if not niche_ids:
        return DashboardSummary(
            total_leads=0,
            qualified_leads=0,
            contacted_leads=0,
            replied_leads=0,
            active_campaigns=0,
            pending_replies=0,
            positive_replies=0,
            lead_status_counts={},
        )

    total_leads = db.scalar(
        select(func.count(Lead.id)).where(Lead.niche_id.in_(niche_ids)),
    ) or 0

    qualified_leads = db.scalar(
        select(func.count(Lead.id)).where(
            Lead.niche_id.in_(niche_ids),
            Lead.status.in_([LeadStatus.QUALIFIED, LeadStatus.READY_FOR_OUTREACH]),
        ),
    ) or 0

    contacted_leads = db.scalar(
        select(func.count(Lead.id)).where(
            Lead.niche_id.in_(niche_ids),
            Lead.status == LeadStatus.CONTACTED,
        ),
    ) or 0

    replied_leads = db.scalar(
        select(func.count(Lead.id)).where(
            Lead.niche_id.in_(niche_ids),
            Lead.status.in_([LeadStatus.REPLIED, LeadStatus.MEETING_BOOKED]),
        ),
    ) or 0

    active_campaigns = db.scalar(
        select(func.count(Campaign.id))
        .join(Niche, Campaign.niche_id == Niche.id)
        .where(Niche.user_id == current_user.id, Campaign.status == CampaignStatus.ACTIVE),
    ) or 0

    pending_replies = db.scalar(
        select(func.count(Reply.id))
        .join(EmailMessage, Reply.email_message_id == EmailMessage.id)
        .join(Lead, EmailMessage.lead_id == Lead.id)
        .where(
            Lead.niche_id.in_(niche_ids),
            Reply.classification == ReplyClassification.UNKNOWN,
        ),
    ) or 0

    positive_replies = db.scalar(
        select(func.count(Reply.id))
        .join(EmailMessage, Reply.email_message_id == EmailMessage.id)
        .join(Lead, EmailMessage.lead_id == Lead.id)
        .where(
            Lead.niche_id.in_(niche_ids),
            Reply.classification == ReplyClassification.POSITIVE,
        ),
    ) or 0

    status_rows = db.execute(
        select(Lead.status, func.count(Lead.id))
        .where(Lead.niche_id.in_(niche_ids))
        .group_by(Lead.status),
    ).all()
    lead_status_counts = {
        (status.value if hasattr(status, "value") else str(status)): count
        for status, count in status_rows
    }

    return DashboardSummary(
        total_leads=total_leads,
        qualified_leads=qualified_leads,
        contacted_leads=contacted_leads,
        replied_leads=replied_leads,
        active_campaigns=active_campaigns,
        pending_replies=pending_replies,
        positive_replies=positive_replies,
        lead_status_counts=lead_status_counts,
    )
