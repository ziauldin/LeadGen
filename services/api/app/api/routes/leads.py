from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_workspace, get_owned_lead
from app.core.config import settings
from app.core.database import get_db
from app.core.tenancy import WorkspaceContext
from app.models.company import Company
from app.models.enums import LeadStatus
from app.models.lead import Lead
from app.models.niche import Niche
from app.schemas.lead import LeadCreate, LeadImportResult, LeadListResponse, LeadRead, LeadUpdate
from app.schemas.outreach import OutreachReadiness
from app.services.billing.usage import check_quota, record_usage
from app.services.compliance.outreach import validate_lead_for_outreach
from app.services.leads.csv_import import export_leads_to_csv, import_leads_from_csv
from app.services.leads.serializers import serialize_lead
from app.services.leads.status import validate_user_status_change

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


@router.get("", response_model=LeadListResponse)
def list_leads(
    niche_id: int | None = None,
    status: LeadStatus | None = None,
    min_score: float | None = Query(default=None, ge=0),
    search: str | None = Query(default=None, max_length=255),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> LeadListResponse:
    conditions = [Lead.workspace_id == ctx.workspace_id]
    if niche_id is not None:
        conditions.append(Lead.niche_id == niche_id)
    if status is not None:
        conditions.append(Lead.status == status)
    if min_score is not None:
        conditions.append(Lead.score >= min_score)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(or_(Lead.full_name.ilike(pattern), Lead.job_title.ilike(pattern)))

    total = db.scalar(select(func.count(Lead.id)).where(*conditions)) or 0
    leads = db.scalars(
        select(Lead)
        .where(*conditions)
        .options(selectinload(Lead.company), selectinload(Lead.email_contacts))
        .order_by(Lead.updated_at.desc(), Lead.id.desc())
        .offset(skip)
        .limit(limit),
    ).all()

    return LeadListResponse(
        items=[serialize_lead(lead) for lead in leads],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def create_lead(
    payload: LeadCreate,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> LeadRead:
    _ensure_niche_in_workspace(db, payload.niche_id, ctx.workspace_id)
    if payload.company_id is not None:
        _ensure_company_in_workspace(db, payload.company_id, ctx.workspace_id)
    data = payload.model_dump()
    data["status"] = validate_user_status_change(LeadStatus.NEW, payload.status)

    check_quota(db, ctx.workspace, "monthly_leads")
    lead = Lead(workspace_id=ctx.workspace_id, **data)
    db.add(lead)
    record_usage(db, ctx.workspace_id, "monthly_leads")
    db.commit()
    return serialize_lead(_load_lead(db, lead.id, ctx.workspace_id))


@router.post("/import-csv", response_model=LeadImportResult)
async def import_csv(
    file: UploadFile = File(...),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
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
) -> LeadRead:
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("company_id") is not None:
        _ensure_company_in_workspace(db, updates["company_id"], ctx.workspace_id)
    if updates.get("status") is not None:
        updates["status"] = validate_user_status_change(lead.status, updates["status"])

    for field, value in updates.items():
        setattr(lead, field, value)

    db.commit()
    return serialize_lead(_load_lead(db, lead.id, ctx.workspace_id))


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(
    lead: Lead = Depends(get_owned_lead),
    db: Session = Depends(get_db),
) -> None:
    db.delete(lead)
    db.commit()
