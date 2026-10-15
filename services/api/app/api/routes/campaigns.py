from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_workspace, get_verified_admin, get_verified_workspace
from app.core.database import get_db
from app.core.rate_limit import enforce
from app.core.tenancy import WorkspaceContext
from app.models.campaign import Campaign
from app.models.enrollment import CampaignEnrollment, EnrollmentStatus
from app.schemas.campaign import (
    AddLeadsRequest,
    AddLeadsResponse,
    CampaignActionResponse,
    CampaignCreate,
    CampaignListResponse,
    CampaignRead,
    CampaignUpdate,
    EnrollmentListResponse,
    EnrollmentRead,
    ProcessSendsResponse,
)
from app.services.campaigns.sequences import stop_enrollment
from app.services.campaigns.service import (
    add_leads_to_campaign,
    create_campaign,
    get_campaign,
    pause_campaign,
    start_campaign,
)
from app.services.campaigns.service import update_campaign as apply_campaign_update
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
        schedule=payload.model_dump(
            include={
                "timezone",
                "sending_days",
                "per_domain_limit",
                "sender_credential_id",
                "stop_on_reply",
            },
        ),
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
    return _serialize_campaign(
        apply_campaign_update(db, campaign, payload.model_dump(exclude_unset=True))
    )


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


@router.get("/{campaign_id}/enrollments", response_model=EnrollmentListResponse)
def list_enrollments(
    campaign_id: int,
    status: str | None = Query(default=None, max_length=20),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> EnrollmentListResponse:
    get_campaign(db, campaign_id, ctx.workspace_id)
    conditions = [
        CampaignEnrollment.campaign_id == campaign_id,
        CampaignEnrollment.workspace_id == ctx.workspace_id,
    ]
    if status:
        conditions.append(CampaignEnrollment.status == status)
    total = db.scalar(select(func.count(CampaignEnrollment.id)).where(*conditions)) or 0
    rows = db.scalars(
        select(CampaignEnrollment)
        .where(*conditions)
        .options(selectinload(CampaignEnrollment.lead))
        .order_by(CampaignEnrollment.id)
        .offset(skip)
        .limit(limit),
    ).all()
    return EnrollmentListResponse(
        items=[
            EnrollmentRead(
                **{
                    key: getattr(row, key)
                    for key in EnrollmentRead.model_fields
                    if key != "lead_name"
                },
                lead_name=row.lead.full_name if row.lead else None,
            )
            for row in rows
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/{campaign_id}/enrollments/{enrollment_id}/stop",
    response_model=EnrollmentRead,
)
def stop_enrollment_endpoint(
    campaign_id: int,
    enrollment_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> EnrollmentRead:
    enrollment = db.scalar(
        select(CampaignEnrollment).where(
            CampaignEnrollment.id == enrollment_id,
            CampaignEnrollment.campaign_id == campaign_id,
            CampaignEnrollment.workspace_id == ctx.workspace_id,
        ),
    )
    if enrollment is None:
        from app.core.errors import NotFoundError

        raise NotFoundError("Enrollment not found")
    stop_enrollment(db, enrollment, EnrollmentStatus.STOPPED, "Stopped manually")
    db.commit()
    db.refresh(enrollment)
    return EnrollmentRead(
        **{
            key: getattr(enrollment, key)
            for key in EnrollmentRead.model_fields
            if key != "lead_name"
        },
        lead_name=None,
    )
