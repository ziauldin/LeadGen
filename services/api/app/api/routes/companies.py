from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.company import Company
from app.models.enums import EnrichmentStatus
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.user import User
from app.schemas.company import CompanyListResponse, CompanyRead, CompanyUpdate, EnrichCompanyResponse
from app.services.companies.helpers import extract_domain, normalize_website
from app.services.enrichment.enricher import enrich_company_record
from app.workers.enrichment_jobs import enrich_company

router = APIRouter(prefix="/companies", tags=["companies"])


def _get_owned_company(
    company_id: int,
    current_user: User,
    db: Session,
) -> Company:
    company = db.scalar(
        select(Company)
        .options(selectinload(Company.email_contacts))
        .join(Lead, Lead.company_id == Company.id)
        .join(Niche, Lead.niche_id == Niche.id)
        .where(Company.id == company_id, Niche.user_id == current_user.id)
        .limit(1),
    )
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.get("", response_model=CompanyListResponse)
def list_companies(
    search: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyListResponse:
    base = (
        select(Company)
        .options(selectinload(Company.email_contacts))
        .join(Lead, Lead.company_id == Company.id)
        .join(Niche, Lead.niche_id == Niche.id)
        .where(Niche.user_id == current_user.id)
        .distinct()
    )
    count_base = (
        select(func.count(func.distinct(Company.id)))
        .join(Lead, Lead.company_id == Company.id)
        .join(Niche, Lead.niche_id == Niche.id)
        .where(Niche.user_id == current_user.id)
    )

    if search:
        pattern = f"%{search.strip()}%"
        base = base.where(Company.name.ilike(pattern))
        count_base = count_base.where(Company.name.ilike(pattern))

    total = db.scalar(count_base) or 0
    companies = db.scalars(base.order_by(Company.name).offset(skip).limit(limit)).all()

    return CompanyListResponse(
        items=[CompanyRead.model_validate(c) for c in companies],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(
    company_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:
    return _get_owned_company(company_id, current_user, db)


@router.patch("/{company_id}", response_model=CompanyRead)
def update_company(
    payload: CompanyUpdate,
    company_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:
    company = _get_owned_company(company_id, current_user, db)

    updates = payload.model_dump(exclude_unset=True)
    if "website" in updates and updates["website"]:
        updates["website"] = normalize_website(updates["website"])
        updates["domain"] = extract_domain(updates["website"])
    if "domain" in updates and updates["domain"]:
        updates["domain"] = updates["domain"].lower()

    for field, value in updates.items():
        setattr(company, field, value)

    db.commit()
    db.refresh(company)
    return company


@router.post("/{company_id}/enrich", response_model=EnrichCompanyResponse)
def enrich_company_endpoint(
    company_id: int,
    sync: bool = Query(default=False, description="Run enrichment inline instead of queueing Celery"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EnrichCompanyResponse:
    company = _get_owned_company(company_id, current_user, db)

    if not company.website:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company has no website to enrich",
        )

    if sync:
        company = enrich_company_record(db, company.id)
        return EnrichCompanyResponse(
            company_id=company.id,
            status=company.enrichment_status.value
            if hasattr(company.enrichment_status, "value")
            else str(company.enrichment_status),
            message=company.enrichment_message or "Enrichment completed",
        )

    company.enrichment_status = EnrichmentStatus.IN_PROGRESS
    company.enrichment_message = "Enrichment queued"
    db.commit()

    enrich_company.delay(company.id)

    return EnrichCompanyResponse(
        company_id=company.id,
        status="queued",
        message="Enrichment job queued",
    )
