from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_workspace, get_verified_admin, get_verified_workspace
from app.core.database import get_db
from app.core.rate_limit import enforce
from app.core.tenancy import WorkspaceContext
from app.models.campaign import Campaign
from app.schemas.campaign import (
    AddLeadsRequest,
    AddLeadsResponse,
    CampaignActionResponse,
    CampaignCreate,
    CampaignListResponse,
    CampaignRead,
    CampaignUpdate,
    ProcessSendsResponse,
)
from app.services.campaigns.service import (
    add_leads_to_campaign,
    create_campaign,
    get_campaign,
    pause_campaign,
    start_campaign,
)
from app.services.sending.sender import process_active_campaigns

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _serialize_campaign(campaign: Campaign) -> CampaignRead:
    return CampaignRead.model_validate(campaign)


@router.get("", response_model=CampaignListResponse)
def list_campaigns(
    niche_id: int | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CampaignListResponse:
    conditions = [Campaign.workspace_id == ctx.workspace_id]
    if niche_id is not None:
        conditions.append(Campaign.niche_id == niche_id)

    total = db.scalar(select(func.count(Campaign.id)).where(*conditions)) or 0
    campaigns = db.scalars(
        select(Campaign)
        .where(*conditions)
        .options(selectinload(Campaign.steps))
        .order_by(Campaign.created_at.desc(), Campaign.id.desc())
        .offset(skip)
        .limit(limit),
    ).all()
    return CampaignListResponse(
        items=[_serialize_campaign(campaign) for campaign in campaigns],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
def create_campaign_endpoint(
    payload: CampaignCreate,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CampaignRead:
    campaign = create_campaign(
        db,
        ctx,
        payload.niche_id,
        payload.name,
        [step.model_dump() for step in payload.steps],
        daily_send_limit=payload.daily_send_limit,
        sending_window_start=payload.sending_window_start,
        sending_window_end=payload.sending_window_end,
    )
    return _serialize_campaign(get_campaign(db, campaign.id, ctx.workspace_id))


@router.get("/{campaign_id}", response_model=CampaignRead)
def get_campaign_endpoint(
    campaign_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CampaignRead:
    return _serialize_campaign(get_campaign(db, campaign_id, ctx.workspace_id))


@router.patch("/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CampaignRead:
    campaign = get_campaign(db, campaign_id, ctx.workspace_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(campaign, field, value)
    db.commit()
    db.refresh(campaign)
    return _serialize_campaign(campaign)


@router.post("/{campaign_id}/add-leads", response_model=AddLeadsResponse)
def add_leads(
    campaign_id: int,
    payload: AddLeadsRequest,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AddLeadsResponse:
    result = add_leads_to_campaign(db, ctx, campaign_id, payload.lead_ids)
    return AddLeadsResponse(
        created=int(result["created"]),
        skipped=int(result["skipped"]),
        errors=list(result["errors"]),
        message_ids=[int(message_id) for message_id in result.get("message_ids", []) if message_id],
    )


@router.post("/{campaign_id}/start", response_model=CampaignActionResponse)
def start_campaign_endpoint(
    campaign_id: int,
    ctx: WorkspaceContext = Depends(get_verified_workspace),
    db: Session = Depends(get_db),
) -> CampaignActionResponse:
    campaign = start_campaign(db, campaign_id, ctx.workspace_id)
    return CampaignActionResponse(
        campaign=_serialize_campaign(campaign), message="Campaign started"
    )


@router.post("/{campaign_id}/pause", response_model=CampaignActionResponse)
def pause_campaign_endpoint(
    campaign_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CampaignActionResponse:
    campaign = pause_campaign(db, campaign_id, ctx.workspace_id)
    return CampaignActionResponse(campaign=_serialize_campaign(campaign), message="Campaign paused")


@router.post("/{campaign_id}/process-sends", response_model=ProcessSendsResponse)
def process_campaign_sends_endpoint(
    campaign_id: int,
    ctx: WorkspaceContext = Depends(get_verified_admin),
    db: Session = Depends(get_db),
) -> ProcessSendsResponse:
    """Send this campaign's approved emails now (admin only). Normally the scheduler does this."""
    get_campaign(db, campaign_id, ctx.workspace_id)
    enforce("10/minute", "process-sends", str(ctx.workspace_id))
    result = process_active_campaigns(
        db,
        actor_id=ctx.user_id,
        workspace_id=ctx.workspace_id,
        campaign_id=campaign_id,
    )
    return ProcessSendsResponse(**result)
