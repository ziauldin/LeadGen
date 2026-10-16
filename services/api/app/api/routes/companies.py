import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_workspace, require_permission
from app.api.paging import PageParams, order_by, page_params
from app.core.database import get_db
from app.core.errors import AppError
from app.core.permissions import Permission
from app.core.tenancy import WorkspaceContext
from app.models.company import Company
from app.models.enums import EnrichmentStatus
from app.schemas.common import BulkIds, BulkResult
from app.schemas.company import (
    CompanyListResponse,
    CompanyRead,
    CompanyUpdate,
    EnrichCompanyResponse,
)
from app.services.billing.usage import check_quota, record_usage
from app.services.companies.helpers import extract_domain, normalize_website
from app.services.enrichment.enricher import enrich_company_record
from app.services.enrichment.queueing import queue_enrichment
from app.services.workspaces.service import audit

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


SORTABLE = {
    "name": Company.name,
    "domain": Company.domain,
    "industry": Company.industry,
    "enrichment_status": Company.enrichment_status,
    "created_at": Company.created_at,
}


@router.get("", response_model=CompanyListResponse)
def list_companies(
    search: str | None = Query(default=None, max_length=255),
    enrichment_status: EnrichmentStatus | None = None,
    page: PageParams = Depends(page_params),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CompanyListResponse:
    skip, limit = page.skip, page.limit
    conditions = [Company.workspace_id == ctx.workspace_id]
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(or_(Company.name.ilike(pattern), Company.domain.ilike(pattern)))
    if enrichment_status is not None:
        conditions.append(Company.enrichment_status == enrichment_status)

    total = db.scalar(select(func.count(Company.id)).where(*conditions)) or 0
    companies = db.scalars(
        select(Company)
        .where(*conditions)
        .options(selectinload(Company.email_contacts))
        .order_by(*order_by(page.sort, SORTABLE, [Company.name.asc()], Company.id))
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
    _allowed: WorkspaceContext = Depends(require_permission(Permission.LEADS_WRITE)),
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
    _allowed: WorkspaceContext = Depends(require_permission(Permission.LEADS_WRITE)),
) -> EnrichCompanyResponse:
    company = _get_company(db, company_id, ctx)

    if not company.website:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company has no website to enrich",
        )
    if sync:
        check_quota(db, ctx.workspace, "daily_enrichments")
        record_usage(db, ctx.workspace_id, "daily_enrichments")
        company = enrich_company_record(db, company.id)
        return EnrichCompanyResponse(
            company_id=company.id,
            status=str(company.enrichment_status),
            message=company.enrichment_message or "Enrichment completed",
        )

    queue_enrichment(db, ctx.workspace, company)

    return EnrichCompanyResponse(
        company_id=company.id,
        status="queued",
        message="Enrichment job queued",
    )


@router.post("/bulk-enrich", response_model=BulkResult)
def bulk_enrich_companies(
    payload: BulkIds,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.LEADS_WRITE)),
) -> BulkResult:
    """Queue enrichment for many companies. Stops charging once the daily quota is used up."""
    result = BulkResult()
    companies = {
        company.id: company
        for company in db.scalars(
            select(Company).where(
                Company.workspace_id == ctx.workspace_id,
                Company.id.in_(payload.ids),
            ),
        ).all()
    }
    for company_id in dict.fromkeys(payload.ids):
        company = companies.get(company_id)
        if company is None:
            result.skip(company_id, "Company not found")
            continue
        if company.enrichment_status == EnrichmentStatus.IN_PROGRESS:
            result.skip(company_id, "Enrichment is already in progress")
            continue
        try:
            queue_enrichment(db, ctx.workspace, company)
        except AppError as exc:
            result.fail(company_id, exc.detail)
            continue
        result.ok(company_id, "queued")
    audit(
        db,
        ctx.workspace_id,
        ctx.user_id,
        "company.bulk_enrich",
        "company",
        None,
        {"succeeded": result.succeeded, "failed": result.failed, "skipped": result.skipped},
    )
    db.commit()
    return result
