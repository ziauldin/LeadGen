"""Public REST API (v1). Authenticated with workspace API keys; see docs/API.md."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.paging import PageParams
from app.api.routes import campaigns as campaign_routes
from app.api.routes import companies as company_routes
from app.api.routes import leads as lead_routes
from app.api.routes import replies as reply_routes
from app.api.routes import settings as settings_routes
from app.api.v1.deps import ApiContext, get_api_context, idempotent, require_scope
from app.core.database import get_db
from app.core.errors import NotFoundError
from app.models.email_contact import EmailContact
from app.models.enums import CampaignStatus, EnrichmentStatus, LeadStatus
from app.models.lead import Lead
from app.schemas.campaign import (
    AddLeadsRequest,
    AddLeadsResponse,
    CampaignListResponse,
    CampaignRead,
    EnrollmentListResponse,
)
from app.schemas.company import CompanyListResponse, CompanyRead
from app.schemas.lead import LeadCreate, LeadListResponse, LeadRead, LeadUpdate
from app.schemas.reply import ReplyListResponse
from app.schemas.suppression import SuppressionCreate, SuppressionListResponse, SuppressionRead
from app.services.billing.usage import check_quota, record_usage
from app.services.developer import events as webhook_events
from app.services.enrichment.email_extractor import classify_email
from app.services.leads.serializers import serialize_lead
from app.services.leads.status import validate_user_status_change

router = APIRouter(prefix="/v1", tags=["public-api"])

PAGE_LIMIT = Query(default=50, ge=1, le=200)


def _page(skip: int, limit: int) -> PageParams:
    return PageParams(skip=skip, limit=limit, sort=None)


class Me(BaseModel):
    workspace_id: int
    workspace_name: str
    key_name: str
    key_prefix: str
    scopes: list[str]


class V1LeadCreate(LeadCreate):
    emails: list[EmailStr] = Field(default_factory=list, max_length=10)


@router.get("/me", response_model=Me)
def me(api: ApiContext = Depends(get_api_context)) -> Me:
    """The workspace and key you're authenticated as."""
    return Me(
        workspace_id=api.ctx.workspace_id,
        workspace_name=api.ctx.workspace.name,
        key_name=api.key.name,
        key_prefix=api.key.prefix,
        scopes=list(api.key.scopes or []),
    )


# --- leads ---------------------------------------------------------------------------------------


@router.get("/leads", response_model=LeadListResponse)
def list_leads(
    niche_id: int | None = None,
    company_id: int | None = None,
    lead_status: LeadStatus | None = Query(default=None, alias="status"),
    has_email: bool | None = None,
    search: str | None = Query(default=None, max_length=255),
    skip: int = Query(default=0, ge=0),
    limit: int = PAGE_LIMIT,
    api: ApiContext = Depends(require_scope("leads:read")),
    db: Session = Depends(get_db),
) -> LeadListResponse:
    return lead_routes.list_leads(
        niche_id=niche_id,
        company_id=company_id,
        status=lead_status,
        min_score=None,
        has_email=has_email,
        search=search,
        page=_page(skip, limit),
        ctx=api.ctx,
        db=db,
    )


def _owned_lead(db: Session, api: ApiContext, lead_id: int) -> Lead:
    lead = db.scalar(
        select(Lead).where(Lead.id == lead_id, Lead.workspace_id == api.ctx.workspace_id)
    )
    if lead is None:
        raise NotFoundError("Lead not found")
    return lead


@router.get("/leads/{lead_id}", response_model=LeadRead)
def get_lead(
    lead_id: int,
    api: ApiContext = Depends(require_scope("leads:read")),
    db: Session = Depends(get_db),
) -> LeadRead:
    _owned_lead(db, api, lead_id)
    return serialize_lead(lead_routes._load_lead(db, lead_id, api.ctx.workspace_id))


@router.post("/leads", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def create_lead(
    payload: V1LeadCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    api: ApiContext = Depends(require_scope("leads:write")),
    db: Session = Depends(get_db),
) -> Any:
    """Create a lead, optionally with email addresses. Supports ``Idempotency-Key``."""

    def run() -> LeadRead:
        ctx = api.ctx
        lead_routes._ensure_niche_in_workspace(db, payload.niche_id, ctx.workspace_id)
        if payload.company_id is not None:
            lead_routes._ensure_company_in_workspace(db, payload.company_id, ctx.workspace_id)
        data = payload.model_dump(exclude={"emails"})
        data["status"] = validate_user_status_change(LeadStatus.NEW, payload.status)
        check_quota(db, ctx.workspace, "monthly_leads")
        lead = Lead(
            workspace_id=ctx.workspace_id,
            source_provider=data.pop("source_provider") or "api",
            **data,
        )
        db.add(lead)
        db.flush()
        emails = sorted({str(e).lower() for e in payload.emails})
        for email in emails:
            email_type, is_role, is_personal, confidence = classify_email(email)
            db.add(
                EmailContact(
                    workspace_id=ctx.workspace_id,
                    lead_id=lead.id,
                    company_id=lead.company_id,
                    email=email,
                    email_type=email_type,
                    is_role_based=is_role,
                    is_personal=is_personal,
                    confidence=confidence,
                    source_url=lead.source_url,
                    source_provider="api",
                )
            )
        webhook_events.lead_created(db, lead, emails)
        record_usage(db, ctx.workspace_id, "monthly_leads")
        db.commit()
        return serialize_lead(lead_routes._load_lead(db, lead.id, ctx.workspace_id))

    return idempotent(db, api, idempotency_key, payload, run, status_code=201)


@router.patch("/leads/{lead_id}", response_model=LeadRead)
def update_lead(
    lead_id: int,
    payload: LeadUpdate,
    api: ApiContext = Depends(require_scope("leads:write")),
    db: Session = Depends(get_db),
) -> LeadRead:
    lead = lead_routes._load_lead(db, _owned_lead(db, api, lead_id).id, api.ctx.workspace_id)
    return lead_routes.update_lead(payload=payload, lead=lead, ctx=api.ctx, db=db, _allowed=api.ctx)


# --- companies -----------------------------------------------------------------------------------


@router.get("/companies", response_model=CompanyListResponse)
def list_companies(
    search: str | None = Query(default=None, max_length=255),
    enrichment_status: EnrichmentStatus | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = PAGE_LIMIT,
    api: ApiContext = Depends(require_scope("leads:read")),
    db: Session = Depends(get_db),
) -> CompanyListResponse:
    return company_routes.list_companies(
        search=search,
        enrichment_status=enrichment_status,
        page=_page(skip, limit),
        ctx=api.ctx,
        db=db,
    )


@router.get("/companies/{company_id}", response_model=CompanyRead)
def get_company(
    company_id: int,
    api: ApiContext = Depends(require_scope("leads:read")),
    db: Session = Depends(get_db),
) -> Any:
    return company_routes.get_company(company_id=company_id, ctx=api.ctx, db=db)


# --- campaigns -----------------------------------------------------------------------------------


@router.get("/campaigns", response_model=CampaignListResponse)
def list_campaigns(
    niche_id: int | None = None,
    campaign_status: CampaignStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = PAGE_LIMIT,
    api: ApiContext = Depends(require_scope("campaigns:read")),
    db: Session = Depends(get_db),
) -> CampaignListResponse:
    return campaign_routes.list_campaigns(
        niche_id=niche_id,
        campaign_status=campaign_status,
        page=_page(skip, limit),
        ctx=api.ctx,
        db=db,
    )


@router.get("/campaigns/{campaign_id}", response_model=CampaignRead)
def get_campaign(
    campaign_id: int,
    api: ApiContext = Depends(require_scope("campaigns:read")),
    db: Session = Depends(get_db),
) -> CampaignRead:
    return campaign_routes.get_campaign_endpoint(campaign_id=campaign_id, ctx=api.ctx, db=db)


@router.get("/campaigns/{campaign_id}/enrollments", response_model=EnrollmentListResponse)
def list_enrollments(
    campaign_id: int,
    enrollment_status: str | None = Query(default=None, alias="status", max_length=20),
    skip: int = Query(default=0, ge=0),
    limit: int = PAGE_LIMIT,
    api: ApiContext = Depends(require_scope("campaigns:read")),
    db: Session = Depends(get_db),
) -> EnrollmentListResponse:
    return campaign_routes.list_enrollments(
        campaign_id=campaign_id,
        status=enrollment_status,
        skip=skip,
        limit=limit,
        ctx=api.ctx,
        db=db,
    )


@router.post("/campaigns/{campaign_id}/enrollments", response_model=AddLeadsResponse)
def enroll_leads(
    campaign_id: int,
    payload: AddLeadsRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    api: ApiContext = Depends(require_scope("campaigns:write")),
    db: Session = Depends(get_db),
) -> Any:
    """Add leads to a campaign. Drafts are created and still go through approval."""
    return idempotent(
        db,
        api,
        idempotency_key,
        {"campaign_id": campaign_id, **payload.model_dump()},
        lambda: campaign_routes.add_leads(
            campaign_id=campaign_id, payload=payload, ctx=api.ctx, db=db, _allowed=api.ctx
        ),
    )


# --- replies -------------------------------------------------------------------------------------


@router.get("/replies", response_model=ReplyListResponse)
def list_replies(
    classification: str | None = Query(default=None, max_length=50),
    campaign_id: int | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = PAGE_LIMIT,
    api: ApiContext = Depends(require_scope("replies:read")),
    db: Session = Depends(get_db),
) -> ReplyListResponse:
    return reply_routes.list_replies(
        classification=classification,
        campaign_id=campaign_id,
        search=None,
        page=_page(skip, limit),
        ctx=api.ctx,
        db=db,
    )


# --- suppressions --------------------------------------------------------------------------------


@router.get("/suppressions", response_model=SuppressionListResponse)
def list_suppressions(
    search: str | None = Query(default=None, max_length=255),
    skip: int = Query(default=0, ge=0),
    limit: int = PAGE_LIMIT,
    api: ApiContext = Depends(require_scope("suppressions:read")),
    db: Session = Depends(get_db),
) -> SuppressionListResponse:
    return settings_routes.list_suppressions(
        skip=skip, limit=limit, search=search, ctx=api.ctx, db=db
    )


@router.post("/suppressions", response_model=SuppressionRead, status_code=status.HTTP_201_CREATED)
def create_suppression(
    payload: SuppressionCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    api: ApiContext = Depends(require_scope("suppressions:write")),
    db: Session = Depends(get_db),
) -> Any:

    def run() -> SuppressionRead:
        suppression = settings_routes.create_suppression(payload=payload, ctx=api.ctx, db=db)
        suppression.source = "api"
        db.commit()
        db.refresh(suppression)
        return SuppressionRead.model_validate(suppression, from_attributes=True)

    return idempotent(db, api, idempotency_key, payload, run, status_code=201)


@router.delete("/suppressions/{suppression_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_suppression(
    suppression_id: int,
    api: ApiContext = Depends(require_scope("suppressions:write")),
    db: Session = Depends(get_db),
) -> None:
    settings_routes.delete_suppression(
        suppression_id=suppression_id, ctx=api.ctx, db=db, _allowed=api.ctx
    )


# --- schema --------------------------------------------------------------------------------------


@router.get("/openapi.json", include_in_schema=False)
def public_openapi() -> dict[str, Any]:
    """OpenAPI document for the public API only."""
    schema = get_openapi(
        title="LeadsGen API",
        version="1.0.0",
        description="Send `Authorization: Bearer <API key>`. Create keys in Settings, under API.",
        routes=router.routes,
    )
    schema["components"] = {
        **schema.get("components", {}),
        "securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}},
    }
    schema["security"] = [{"bearer": []}]
    return schema
