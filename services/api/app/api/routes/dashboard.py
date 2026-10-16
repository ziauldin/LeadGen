from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace
from app.core.database import get_db
from app.core.tenancy import WorkspaceContext
from app.models.campaign import Campaign
from app.models.email_message import EmailMessage
from app.models.enums import CampaignStatus, EmailMessageStatus, LeadStatus, ReplyClassification
from app.models.lead import Lead
from app.models.reply import Reply
from app.models.suppression import Suppression

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardSummary(BaseModel):
    total_leads: int
    qualified_leads: int
    contacted_leads: int
    replied_leads: int
    active_campaigns: int
    pending_replies: int
    positive_replies: int
    pending_approval: int
    approved_emails: int
    sent_today: int
    opted_out_leads: int
    suppressed_contacts: int
    lead_status_counts: dict[str, int]


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    ws = ctx.workspace_id

    def count(model, *conditions) -> int:
        return (
            db.scalar(select(func.count(model.id)).where(model.workspace_id == ws, *conditions))
            or 0
        )

    status_rows = db.execute(
        select(Lead.status, func.count(Lead.id))
        .where(Lead.workspace_id == ws)
        .group_by(Lead.status),
    ).all()
    lead_status_counts = {str(status): total for status, total in status_rows}

    start_of_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    return DashboardSummary(
        total_leads=count(Lead),
        qualified_leads=count(
            Lead,
            Lead.status.in_([LeadStatus.QUALIFIED, LeadStatus.READY_FOR_OUTREACH]),
        ),
        contacted_leads=count(Lead, Lead.status == LeadStatus.CONTACTED),
        replied_leads=count(
            Lead,
            Lead.status.in_([LeadStatus.REPLIED, LeadStatus.MEETING_BOOKED]),
        ),
        active_campaigns=count(Campaign, Campaign.status == CampaignStatus.ACTIVE),
        pending_replies=count(Reply, Reply.classification == ReplyClassification.UNKNOWN),
        positive_replies=count(Reply, Reply.classification == ReplyClassification.POSITIVE),
        pending_approval=count(
            EmailMessage,
            EmailMessage.status.in_(
                [EmailMessageStatus.DRAFT, EmailMessageStatus.PENDING_APPROVAL],
            ),
        ),
        approved_emails=count(EmailMessage, EmailMessage.status == EmailMessageStatus.APPROVED),
        sent_today=count(
            EmailMessage,
            EmailMessage.status == EmailMessageStatus.SENT,
            EmailMessage.sent_at >= start_of_day,
        ),
        opted_out_leads=count(Lead, Lead.status == LeadStatus.OPTED_OUT),
        suppressed_contacts=count(Suppression),
        lead_status_counts=lead_status_counts,
    )
