from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_owned_lead
from app.core.database import get_db
from app.models.company import Company
from app.models.enums import LeadStatus
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.user import User
from app.schemas.lead import LeadCreate, LeadImportResult, LeadListResponse, LeadRead, LeadUpdate
from app.schemas.outreach import OutreachReadiness
from app.services.compliance.outreach import validate_lead_for_outreach
from app.services.leads.csv_import import export_leads_to_csv, import_leads_from_csv
from app.services.leads.serializers import serialize_lead

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=LeadListResponse)
def list_leads(
    niche_id: int | None = None,
    status: LeadStatus | None = None,
    min_score: float | None = Query(default=None, ge=0),
    search: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadListResponse:
    query = (
        select(Lead)
        .join(Niche, Lead.niche_id == Niche.id)
        .where(Niche.user_id == current_user.id)
        .options(selectinload(Lead.company), selectinload(Lead.email_contacts))
    )
    count_query = (
        select(func.count(Lead.id))
        .join(Niche, Lead.niche_id == Niche.id)
        .where(Niche.user_id == current_user.id)
    )

    if niche_id is not None:
        query = query.where(Lead.niche_id == niche_id)
        count_query = count_query.where(Lead.niche_id == niche_id)
    if status is not None:
        query = query.where(Lead.status == status)
        count_query = count_query.where(Lead.status == status)
    if min_score is not None:
        query = query.where(Lead.score >= min_score)
        count_query = count_query.where(Lead.score >= min_score)
    if search:
        pattern = f"%{search.strip()}%"
        filter_clause = or_(
            Lead.full_name.ilike(pattern),
            Lead.job_title.ilike(pattern),
        )
        query = query.where(filter_clause)
        count_query = count_query.where(filter_clause)

    total = db.scalar(count_query) or 0
    leads = db.scalars(
        query.order_by(Lead.updated_at.desc()).offset(skip).limit(limit),
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadRead:
    niche = db.scalar(
        select(Niche).where(Niche.id == payload.niche_id, Niche.user_id == current_user.id),
    )
    if niche is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niche not found")

    if payload.company_id is not None:
        company = db.get(Company, payload.company_id)
        if company is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    lead = Lead(**payload.model_dump())
    db.add(lead)
    db.commit()
    db.refresh(lead)
    lead = db.scalar(
        select(Lead)
        .where(Lead.id == lead.id)
        .options(selectinload(Lead.company), selectinload(Lead.email_contacts)),
    )
    assert lead is not None
    return serialize_lead(lead)


@router.post("/import-csv", response_model=LeadImportResult)
async def import_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadImportResult:
    content = (await file.read()).decode("utf-8-sig")
    result = import_leads_from_csv(db, current_user, content)
    return LeadImportResult(
        created=result.created,
        updated=result.updated,
        skipped=result.skipped,
        errors=result.errors,
    )


@router.get("/export-csv")
def export_csv(
    niche_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    if niche_id is not None:
        niche = db.scalar(
            select(Niche).where(Niche.id == niche_id, Niche.user_id == current_user.id),
        )
        if niche is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niche not found")

    csv_content = export_leads_to_csv(db, current_user, niche_id)
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
    db: Session = Depends(get_db),
) -> LeadRead:
    if payload.company_id is not None:
        company = db.get(Company, payload.company_id)
        if company is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)

    db.commit()
    db.refresh(lead)
    lead = db.scalar(
        select(Lead)
        .where(Lead.id == lead.id)
        .options(selectinload(Lead.company), selectinload(Lead.email_contacts)),
    )
    assert lead is not None
    return serialize_lead(lead)


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(
    lead: Lead = Depends(get_owned_lead),
    db: Session = Depends(get_db),
) -> None:
    db.delete(lead)
    db.commit()
