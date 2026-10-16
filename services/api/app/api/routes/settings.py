from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace, require_permission
from app.core.config import settings as app_settings
from app.core.database import get_db
from app.core.permissions import Permission
from app.core.rate_limit import enforce
from app.core.tenancy import WorkspaceContext
from app.models.enums import ProviderType
from app.models.suppression import Suppression
from app.models.workspace import WorkspaceSettings
from app.schemas.settings import DeliverabilityReport, UserSettingsRead, UserSettingsUpdate
from app.schemas.suppression import SuppressionCreate, SuppressionListResponse, SuppressionRead
from app.services.compliance.freemail import is_freemail_domain
from app.services.deliverability import run_checks, valid_domain
from app.services.provider_credentials.service import (
    decrypt_provider_config,
    get_active_credential,
)
from app.services.workspaces.service import audit, get_or_create_settings

router = APIRouter(prefix="/settings", tags=["settings"])
suppressions_router = APIRouter(prefix="/suppressions", tags=["suppressions"])


@router.get("", response_model=UserSettingsRead)
def get_settings(
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> WorkspaceSettings:
    return get_or_create_settings(db, ctx.workspace_id)


@router.patch("", response_model=UserSettingsRead)
def update_settings(
    payload: UserSettingsUpdate,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.SETTINGS_MANAGE)),
) -> WorkspaceSettings:
    workspace_settings = get_or_create_settings(db, ctx.workspace_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field in ("ai_mode", "block_risky_emails", "auto_create_deals") and value is None:
            continue
        setattr(workspace_settings, field, value)
    db.commit()
    db.refresh(workspace_settings)
    return workspace_settings


def _visible(ctx: WorkspaceContext):
    return or_(Suppression.workspace_id == ctx.workspace_id, Suppression.workspace_id.is_(None))


@router.get("/deliverability", response_model=DeliverabilityReport)
def deliverability_check(
    domain: str | None = Query(default=None, max_length=253),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> DeliverabilityReport:
    """Check SPF, DKIM, DMARC and MX for the sending domain (defaults to the active sender)."""
    enforce("10/minute", "deliverability", str(ctx.workspace_id))
    credential = get_active_credential(db, ctx.workspace_id, ProviderType.EMAIL)
    provider = str(credential.provider_name) if credential else None
    if not domain and credential is not None:
        from_email = str(decrypt_provider_config(credential).get("from_email") or "")
        domain = from_email.rsplit("@", 1)[-1] if "@" in from_email else None
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Give a domain, or set up a sending account with a from address first",
        )
    if not valid_domain(domain):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid domain")
    report = run_checks(
        domain,
        provider=provider,
        inbound_domain=app_settings.inbound_email_domain or None,
    )
    return DeliverabilityReport.model_validate(report)


@suppressions_router.get("", response_model=SuppressionListResponse)
def list_suppressions(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    search: str | None = Query(default=None, max_length=255),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> SuppressionListResponse:
    conditions = [Suppression.workspace_id == ctx.workspace_id]
    if search:
        pattern = f"%{search.strip().lower()}%"
        conditions.append(or_(Suppression.email.ilike(pattern), Suppression.domain.ilike(pattern)))
    total = db.scalar(select(func.count(Suppression.id)).where(*conditions)) or 0
    items = db.scalars(
        select(Suppression)
        .where(*conditions)
        .order_by(Suppression.created_at.desc())
        .offset(skip)
        .limit(limit),
    ).all()
    return SuppressionListResponse(
        items=[SuppressionRead.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@suppressions_router.post("", response_model=SuppressionRead, status_code=status.HTTP_201_CREATED)
def create_suppression(
    payload: SuppressionCreate,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> Suppression:
    email = payload.email.lower().strip() if payload.email else None
    domain = (
        None if email else (payload.domain.lower().strip().lstrip("@") if payload.domain else None)
    )

    if domain and is_freemail_domain(domain):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{domain} is a shared email provider. Suppress individual addresses instead.",
        )

    existing_query = select(Suppression.id).where(Suppression.workspace_id == ctx.workspace_id)
    if email:
        existing_query = existing_query.where(Suppression.email == email)
    else:
        existing_query = existing_query.where(
            Suppression.email.is_(None),
            Suppression.domain == domain,
        )
    if db.scalar(existing_query) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Suppression already exists"
        )

    suppression = Suppression(
        workspace_id=ctx.workspace_id,
        email=email,
        domain=domain,
        reason=payload.reason,
        source="manual",
    )
    db.add(suppression)
    db.flush()
    audit(
        db,
        ctx.workspace_id,
        ctx.user_id,
        "suppression_created",
        "suppression",
        suppression.id,
        {"email": email, "domain": domain},
    )
    db.commit()
    db.refresh(suppression)
    return suppression


@suppressions_router.delete("/{suppression_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_suppression(
    suppression_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.SETTINGS_MANAGE)),
) -> None:
    suppression = db.scalar(
        select(Suppression).where(
            Suppression.id == suppression_id,
            Suppression.workspace_id == ctx.workspace_id,
        ),
    )
    if suppression is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suppression not found")
    audit(
        db,
        ctx.workspace_id,
        ctx.user_id,
        "suppression_deleted",
        "suppression",
        suppression.id,
        {"email": suppression.email, "domain": suppression.domain},
    )
    db.delete(suppression)
    db.commit()
