import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_workspace
from app.core.database import get_db
from app.core.tenancy import WorkspaceContext
from app.models.company import Company
from app.models.enums import EnrichmentStatus
from app.schemas.company import (
    CompanyListResponse,
    CompanyRead,
    CompanyUpdate,
    EnrichCompanyResponse,
)
from app.services.billing.usage import check_quota, record_usage
from app.services.companies.helpers import extract_domain, normalize_website
from app.services.enrichment.enricher import enrich_company_record
from app.workers.enrichment_jobs import enrich_company

router = APIRouter(prefix="/companies", tags=["companies"])
logger = logging.getLogger(__name__)


def _get_company(db: Session, company_id: int, ctx: WorkspaceContext) -> Company:
    company = db.scalar(
        select(Company)
        .where(Company.id == company_id, Company.workspace_id == ctx.workspace_id)
        .options(selectinload(Company.email_contacts)),
    )
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.get("", response_model=CompanyListResponse)
def list_companies(
    search: str | None = Query(default=None, max_length=255),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CompanyListResponse:
    conditions = [Company.workspace_id == ctx.workspace_id]
    if search:
        conditions.append(Company.name.ilike(f"%{search.strip()}%"))

    total = db.scalar(select(func.count(Company.id)).where(*conditions)) or 0
    companies = db.scalars(
        select(Company)
        .where(*conditions)
        .options(selectinload(Company.email_contacts))
        .order_by(Company.name)
        .offset(skip)
        .limit(limit),
    ).all()

    return CompanyListResponse(
        items=[CompanyRead.model_validate(c) for c in companies],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(
    company_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> Company:
    return _get_company(db, company_id, ctx)


@router.patch("/{company_id}", response_model=CompanyRead)
def update_company(
    payload: CompanyUpdate,
    company_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> Company:
    company = _get_company(db, company_id, ctx)

    updates = payload.model_dump(exclude_unset=True)
    if updates.get("website"):
        updates["website"] = normalize_website(updates["website"])
        updates["domain"] = extract_domain(updates["website"])
    if updates.get("domain"):
        updates["domain"] = updates["domain"].lower()

    for field, value in updates.items():
        setattr(company, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another company in this workspace already uses that domain",
        ) from None
    db.refresh(company)
    return company


@router.post("/{company_id}/enrich", response_model=EnrichCompanyResponse)
def enrich_company_endpoint(
    company_id: int,
    sync: bool = Query(default=False, description="Run inline instead of on a worker"),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> EnrichCompanyResponse:
    company = _get_company(db, company_id, ctx)

    if not company.website:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company has no website to enrich",
        )
    check_quota(db, ctx.workspace, "daily_enrichments")
    record_usage(db, ctx.workspace_id, "daily_enrichments")

    if sync:
        company = enrich_company_record(db, company.id)
        return EnrichCompanyResponse(
            company_id=company.id,
            status=str(company.enrichment_status),
            message=company.enrichment_message or "Enrichment completed",
        )

    previous_status = company.enrichment_status
    previous_message = company.enrichment_message
    company.enrichment_status = EnrichmentStatus.IN_PROGRESS
    company.enrichment_message = "Enrichment queued"
    db.commit()

    try:
        enrich_company.delay(company.id)
    except Exception as exc:
        logger.warning("Could not queue enrichment for company %s: %s", company.id, exc)
        company.enrichment_status = previous_status
        company.enrichment_message = previous_message
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Background workers are unavailable. Try again shortly, or run it inline.",
        ) from None

    return EnrichCompanyResponse(
        company_id=company.id,
        status="queued",
        message="Enrichment job queued",
    )
