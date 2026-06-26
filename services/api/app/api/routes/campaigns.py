from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.campaign import Campaign
from app.models.niche import Niche
from app.models.user import User
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
    pause_campaign,
    start_campaign,
)
from app.services.sending.sender import process_active_campaigns

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _serialize_campaign(campaign: Campaign) -> CampaignRead:
    return CampaignRead.model_validate(campaign)


def _get_owned_campaign_or_404(
    db: Session,
    campaign_id: int,
    user_id: int,
) -> Campaign:
    campaign = db.scalar(
        select(Campaign)
        .join(Niche, Campaign.niche_id == Niche.id)
        .where(Campaign.id == campaign_id, Niche.user_id == user_id)
        .options(selectinload(Campaign.steps)),
    )
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign


@router.get("", response_model=CampaignListResponse)
def list_campaigns(
    niche_id: int | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignListResponse:
    query = (
        select(Campaign)
        .join(Niche, Campaign.niche_id == Niche.id)
        .where(Niche.user_id == current_user.id)
        .options(selectinload(Campaign.steps))
    )
    count_query = (
        select(func.count(Campaign.id))
        .join(Niche, Campaign.niche_id == Niche.id)
        .where(Niche.user_id == current_user.id)
    )
    if niche_id is not None:
        query = query.where(Campaign.niche_id == niche_id)
        count_query = count_query.where(Campaign.niche_id == niche_id)

    total = db.scalar(count_query) or 0
    campaigns = db.scalars(query.order_by(Campaign.created_at.desc()).offset(skip).limit(limit)).all()
    return CampaignListResponse(
        items=[_serialize_campaign(campaign) for campaign in campaigns],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
def create_campaign_endpoint(
    payload: CampaignCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignRead:
    try:
        campaign = create_campaign(
            db,
            current_user.id,
            payload.niche_id,
            payload.name,
            [step.model_dump() for step in payload.steps],
            daily_send_limit=payload.daily_send_limit,
            sending_window_start=payload.sending_window_start,
            sending_window_end=payload.sending_window_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    campaign = _get_owned_campaign_or_404(db, campaign.id, current_user.id)
    return _serialize_campaign(campaign)


@router.get("/{campaign_id}", response_model=CampaignRead)
def get_campaign(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignRead:
    campaign = _get_owned_campaign_or_404(db, campaign_id, current_user.id)
    return _serialize_campaign(campaign)


@router.patch("/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignRead:
    campaign = _get_owned_campaign_or_404(db, campaign_id, current_user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(campaign, field, value)
    db.commit()
    db.refresh(campaign)
    return _serialize_campaign(campaign)


@router.post("/{campaign_id}/add-leads", response_model=AddLeadsResponse)
def add_leads(
    campaign_id: int,
    payload: AddLeadsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AddLeadsResponse:
    try:
        result = add_leads_to_campaign(db, campaign_id, current_user.id, payload.lead_ids)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return AddLeadsResponse(
        created=int(result["created"]),
        skipped=int(result["skipped"]),
        errors=list(result["errors"]),
        message_ids=[int(message_id) for message_id in result.get("message_ids", []) if message_id],
    )


@router.post("/{campaign_id}/start", response_model=CampaignActionResponse)
def start_campaign_endpoint(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignActionResponse:
    try:
        campaign = start_campaign(db, campaign_id, current_user.id)
    except ValueError as exc:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    return CampaignActionResponse(
        campaign=_serialize_campaign(campaign),
        message="Campaign started",
    )


@router.post("/{campaign_id}/pause", response_model=CampaignActionResponse)
def pause_campaign_endpoint(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignActionResponse:
    try:
        campaign = pause_campaign(db, campaign_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return CampaignActionResponse(
        campaign=_serialize_campaign(campaign),
        message="Campaign paused",
    )


@router.post("/{campaign_id}/process-sends", response_model=ProcessSendsResponse)
def process_campaign_sends_endpoint(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProcessSendsResponse:
    _get_owned_campaign_or_404(db, campaign_id, current_user.id)
    result = process_active_campaigns(db, actor_id=current_user.id)
    return ProcessSendsResponse(**result)
