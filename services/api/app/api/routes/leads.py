from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_workspace, get_owned_lead, require_permission
from app.api.paging import PageParams, order_by, page_params
from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import Permission
from app.core.tenancy import WorkspaceContext
from app.models.company import Company
from app.models.email_contact import EmailContact
from app.models.enums import LeadStatus
from app.models.lead import Lead
from app.models.niche import Niche
from app.schemas.common import BulkResult
from app.schemas.lead import (
    LeadBulkRequest,
    LeadCreate,
    LeadImportResult,
    LeadListResponse,
    LeadRead,
    LeadStats,
    LeadUpdate,
)
from app.schemas.outreach import OutreachReadiness
from app.services.billing.usage import check_quota, record_usage
from app.services.compliance.outreach import validate_lead_for_outreach
from app.services.developer import events as webhook_events
from app.services.leads.bulk import delete_lead as remove_lead
from app.services.leads.bulk import lead_stats, run_bulk_action
from app.services.leads.csv_import import export_leads_to_csv, import_leads_from_csv
from app.services.leads.serializers import serialize_lead
from app.services.leads.status import validate_user_status_change
from app.services.verification.service import queue_auto_verification

router = APIRouter(prefix="/leads", tags=["leads"])


def _load_lead(db: Session, lead_id: int, workspace_id: int) -> Lead:
    lead = db.scalar(
        select(Lead)
        .where(Lead.id == lead_id, Lead.workspace_id == workspace_id)
        .options(selectinload(Lead.company), selectinload(Lead.email_contacts)),
    )
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


def _ensure_company_in_workspace(db: Session, company_id: int, workspace_id: int) -> None:
    company = db.scalar(
        select(Company.id).where(Company.id == company_id, Company.workspace_id == workspace_id),
    )
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")


def _ensure_niche_in_workspace(db: Session, niche_id: int, workspace_id: int) -> None:
    niche = db.scalar(
        select(Niche.id).where(Niche.id == niche_id, Niche.workspace_id == workspace_id),
    )
    if niche is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niche not found")


SORTABLE = {
    "full_name": Lead.full_name,
    "job_title": Lead.job_title,
    "score": Lead.score,
    "status": Lead.status,
    "created_at": Lead.created_at,
    "updated_at": Lead.updated_at,
}


@router.get("", response_model=LeadListResponse)
def list_leads(
    niche_id: int | None = None,
    company_id: int | None = None,
    status: LeadStatus | None = None,
    min_score: float | None = Query(default=None, ge=0),
    has_email: bool | None = None,
    search: str | None = Query(default=None, max_length=255),
    page: PageParams = Depends(page_params),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> LeadListResponse:
    skip, limit = page.skip, page.limit
    conditions = [Lead.workspace_id == ctx.workspace_id]
    if company_id is not None:
        conditions.append(Lead.company_id == company_id)
    if has_email is not None:
        with_email = exists().where(
            EmailContact.lead_id == Lead.id,
            EmailContact.opted_out.is_(False),
        )
        conditions.append(with_email if has_email else ~with_email)
    if niche_id is not None:
        conditions.append(Lead.niche_id == niche_id)
    if status is not None:
        conditions.append(Lead.status == status)
    if min_score is not None:
        conditions.append(Lead.score >= min_score)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                Lead.full_name.ilike(pattern),
                Lead.job_title.ilike(pattern),
                Lead.company.has(Company.name.ilike(pattern)),
            ),
        )

    total = db.scalar(select(func.count(Lead.id)).where(*conditions)) or 0
    leads = db.scalars(
        select(Lead)
        .where(*conditions)
        .options(selectinload(Lead.company), selectinload(Lead.email_contacts))
        .order_by(*order_by(page.sort, SORTABLE, [Lead.updated_at.desc()], Lead.id))
        .offset(skip)
        .limit(limit),
    ).all()

    return LeadListResponse(
        items=[serialize_lead(lead) for lead in leads],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/stats", response_model=LeadStats)
def get_lead_stats(
    niche_id: int | None = None,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> LeadStats:
    return lead_stats(db, ctx.workspace_id, niche_id=niche_id)


@router.post("/bulk", response_model=BulkResult)
def bulk_leads(
    payload: LeadBulkRequest,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.LEADS_WRITE)),
) -> BulkResult:
    """Add to a campaign, enrich, change status, rescore or delete up to 500 leads at once."""
    if payload.action == "delete" and not ctx.can(Permission.LEADS_DELETE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Your role can't delete leads"
        )
    return run_bulk_action(db, ctx, payload)


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def create_lead(
    payload: LeadCreate,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.LEADS_WRITE)),
) -> LeadRead:
    _ensure_niche_in_workspace(db, payload.niche_id, ctx.workspace_id)
    if payload.company_id is not None:
        _ensure_company_in_workspace(db, payload.company_id, ctx.workspace_id)
    data = payload.model_dump()
    data["status"] = validate_user_status_change(LeadStatus.NEW, payload.status)

    check_quota(db, ctx.workspace, "monthly_leads")
    lead = Lead(workspace_id=ctx.workspace_id, **data)
    db.add(lead)
    db.flush()
    webhook_events.lead_created(db, lead)
    record_usage(db, ctx.workspace_id, "monthly_leads")
    db.commit()
    return serialize_lead(_load_lead(db, lead.id, ctx.workspace_id))


@router.post("/import-csv", response_model=LeadImportResult)
async def import_csv(
    file: UploadFile = File(...),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.LEADS_WRITE)),
) -> LeadImportResult:
    raw = await file.read(settings.csv_max_bytes + 1)
    if len(raw) > settings.csv_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"CSV file is larger than {settings.csv_max_bytes // 1_000_000} MB",
        )
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file must be UTF-8 encoded",
        ) from None
    result = import_leads_from_csv(db, ctx.workspace_id, content, workspace=ctx.workspace)
    queue_auto_verification(db, ctx.workspace_id)
    return LeadImportResult(
        created=result.created,
        updated=result.updated,
        skipped=result.skipped,
        errors=result.errors,
    )


@router.get("/export-csv")
def export_csv(
    niche_id: int | None = None,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.DATA_EXPORT)),
) -> PlainTextResponse:
    if niche_id is not None:
        _ensure_niche_in_workspace(db, niche_id, ctx.workspace_id)
    csv_content = export_leads_to_csv(db, ctx.workspace_id, niche_id)
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )


@router.get("/{lead_id}/outreach-readiness", response_model=OutreachReadiness)
def get_lead_outreach_readiness(
    lead: Lead = Depends(get_owned_lead),
    db: Session = Depends(get_db),
) -> OutreachReadiness:
    issues = validate_lead_for_outreach(lead, db)
    return OutreachReadiness(ready=len(issues) == 0, issues=issues)


@router.get("/{lead_id}", response_model=LeadRead)
def get_lead(lead: Lead = Depends(get_owned_lead)) -> LeadRead:
    return serialize_lead(lead)


@router.patch("/{lead_id}", response_model=LeadRead)
def update_lead(
    payload: LeadUpdate,
    lead: Lead = Depends(get_owned_lead),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.LEADS_WRITE)),
) -> LeadRead:
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("company_id") is not None:
        _ensure_company_in_workspace(db, updates["company_id"], ctx.workspace_id)
    if updates.get("status") is not None:
        updates["status"] = validate_user_status_change(lead.status, updates["status"])
    if "lawful_basis" in updates and updates["lawful_basis"] is None:
        del updates["lawful_basis"]  # a lead always keeps a basis

    for field, value in updates.items():
        setattr(lead, field, value)

    db.commit()
    return serialize_lead(_load_lead(db, lead.id, ctx.workspace_id))


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(
    lead: Lead = Depends(get_owned_lead),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.LEADS_DELETE)),
) -> None:
    remove_lead(db, lead)
    db.commit()
