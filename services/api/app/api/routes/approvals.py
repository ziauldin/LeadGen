from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_workspace, get_verified_workspace
from app.api.paging import PageParams, order_by, page_params
from app.core.database import get_db
from app.core.tenancy import WorkspaceContext
from app.models.email_message import EmailMessage
from app.models.lead import Lead
from app.schemas.approval import (
    ApprovalItem,
    ApprovalLead,
    ApprovalQueue,
    BulkApproveRequest,
    BulkRejectRequest,
)
from app.schemas.common import BulkResult
from app.services.approvals.service import (
    bulk_approve,
    bulk_reject,
    campaign_names,
    queue_counts,
    queue_query,
    review_problems,
)

router = APIRouter(prefix="/approvals", tags=["approvals"])

SORTABLE = {
    "created_at": EmailMessage.created_at,
    "scheduled_for": EmailMessage.scheduled_for,
    "step_number": EmailMessage.step_number,
    "recipient_email": EmailMessage.recipient_email,
}


def approval_item(
    db: Session,
    message: EmailMessage,
    campaign_name: str | None,
) -> ApprovalItem:
    lead = message.lead
    company = lead.company if lead else None
    problems = review_problems(db, message, lead)
    return ApprovalItem(
        id=message.id,
        status=str(message.status),
        recipient_email=message.recipient_email,
        subject=message.subject,
        body=message.body,
        step_number=message.step_number,
        scheduled_for=message.scheduled_for,
        created_at=message.created_at,
        campaign_id=message.campaign_id,
        campaign_name=campaign_name,
        lead=ApprovalLead(
            id=lead.id,
            full_name=lead.full_name,
            job_title=lead.job_title,
            company_name=company.name if company else None,
            company_domain=company.domain if company else None,
            score=lead.score,
            status=str(lead.status),
        )
        if lead
        else None,
        generation_mode=message.generation_mode,
        generation_note=message.generation_note,
        llm_model=message.llm_model,
        template_id=message.template_id,
        edited_at=message.edited_at,
        problems=problems,
        can_approve=not problems,
    )


@router.get("", response_model=ApprovalQueue)
def list_approvals(
    campaign_id: int | None = None,
    mode: str | None = Query(default=None, pattern="^(template|ai|template_fallback)$"),
    page: PageParams = Depends(page_params),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ApprovalQueue:
    """Drafts waiting for a decision, with live compliance checks for each."""
    query = queue_query(ctx.workspace_id, campaign_id=campaign_id, mode=mode)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    messages = db.scalars(
        query.options(
            selectinload(EmailMessage.lead).selectinload(Lead.email_contacts),
            selectinload(EmailMessage.lead).selectinload(Lead.company),
        )
        .order_by(
            *order_by(
                page.sort,
                SORTABLE,
                [EmailMessage.scheduled_for.asc(), EmailMessage.created_at.asc()],
                EmailMessage.id,
            ),
        )
        .offset(page.skip)
        .limit(page.limit),
    ).all()
    names = campaign_names(db, {m.campaign_id for m in messages if m.campaign_id})
    return ApprovalQueue(
        items=[approval_item(db, m, names.get(m.campaign_id or 0)) for m in messages],
        total=total,
        skip=page.skip,
        limit=page.limit,
        by_campaign=queue_counts(db, ctx.workspace_id),
    )


@router.post("/bulk-approve", response_model=BulkResult)
def bulk_approve_endpoint(
    payload: BulkApproveRequest,
    ctx: WorkspaceContext = Depends(get_verified_workspace),
    db: Session = Depends(get_db),
) -> BulkResult:
    return bulk_approve(db, ctx.workspace_id, payload.message_ids, actor_id=ctx.user_id)


@router.post("/bulk-reject", response_model=BulkResult)
def bulk_reject_endpoint(
    payload: BulkRejectRequest,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> BulkResult:
    return bulk_reject(
        db,
        ctx.workspace_id,
        payload.message_ids,
        reason=payload.reason,
        actor_id=ctx.user_id,
    )
