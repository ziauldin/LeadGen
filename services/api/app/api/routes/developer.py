"""API keys and outbound webhook endpoints (Settings > API)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace, require_permission
from app.core.database import get_db
from app.core.errors import NotFoundError
from app.core.flags import feature_enabled
from app.core.permissions import Permission
from app.core.tenancy import WorkspaceContext
from app.models.developer import ApiKey, WebhookDelivery, WebhookEndpoint
from app.models.user import User
from app.services.billing.plans import require_feature
from app.services.developer.api_keys import SCOPES, create_api_key, validate_scopes
from app.services.developer.webhooks import (
    EVENTS,
    new_secret,
    replay,
    send_test_event,
    set_secret,
    validate_endpoint_url,
    validate_events,
)
from app.services.workspaces.service import audit

router = APIRouter(tags=["developer"])

MANAGE = Depends(require_permission(Permission.API_KEYS_MANAGE))


def _enabled(ctx: WorkspaceContext) -> None:
    if not feature_enabled("public_api", ctx.workspace):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="The public API isn't enabled"
        )
    require_feature(ctx.workspace, "api_access", "The API")


class OptionRead(BaseModel):
    key: str
    description: str


class DeveloperOptions(BaseModel):
    enabled: bool
    scopes: list[OptionRead]
    events: list[OptionRead]


class ApiKeyRead(BaseModel):
    id: int
    name: str
    prefix: str
    scopes: list[str]
    created_by: str | None
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    scopes: list[str]
    expires_in_days: int | None = Field(default=None, ge=1, le=730)


class ApiKeyCreated(ApiKeyRead):
    key: str  # shown once


class EndpointRead(BaseModel):
    id: int
    url: str
    description: str | None
    events: list[str]
    is_active: bool
    disabled_reason: str | None
    consecutive_failures: int
    created_at: datetime


class EndpointCreated(EndpointRead):
    secret: str  # shown once


class EndpointWrite(BaseModel):
    url: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=255)
    events: list[str] | None = None
    is_active: bool | None = None


class SecretRead(BaseModel):
    secret: str


class DeliveryRead(BaseModel):
    id: int
    event_id: str
    event_type: str
    status: str
    attempts: int
    response_status: int | None
    error: str | None
    created_at: datetime
    delivered_at: datetime | None
    next_attempt_at: datetime | None


class DeliveryPage(BaseModel):
    items: list[DeliveryRead]
    total: int


def _key_read(key: ApiKey, created_by: str | None) -> dict:
    return {
        "id": key.id,
        "name": key.name,
        "prefix": key.prefix,
        "scopes": key.scopes,
        "created_by": created_by,
        "created_at": key.created_at,
        "last_used_at": key.last_used_at,
        "expires_at": key.expires_at,
        "revoked_at": key.revoked_at,
    }


def _endpoint_read(endpoint: WebhookEndpoint) -> dict:
    return {
        "id": endpoint.id,
        "url": endpoint.url,
        "description": endpoint.description,
        "events": endpoint.events,
        "is_active": endpoint.is_active,
        "disabled_reason": endpoint.disabled_reason,
        "consecutive_failures": endpoint.consecutive_failures,
        "created_at": endpoint.created_at,
    }


@router.get("/developer/options", response_model=DeveloperOptions)
def developer_options(ctx: WorkspaceContext = Depends(get_current_workspace)) -> DeveloperOptions:
    return DeveloperOptions(
        enabled=feature_enabled("public_api", ctx.workspace),
        scopes=[OptionRead(key=k, description=v[0]) for k, v in SCOPES.items()],
        events=[OptionRead(key=k, description=v) for k, v in EVENTS.items()],
    )


# --- API keys ----------------------------------------------------------------------------------


@router.get("/api-keys", response_model=list[ApiKeyRead])
def list_api_keys(
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = MANAGE,
) -> list[ApiKeyRead]:
    rows = db.execute(
        select(ApiKey, User.name)
        .join(User, User.id == ApiKey.created_by_id, isouter=True)
        .where(ApiKey.workspace_id == ctx.workspace_id)
        .order_by(ApiKey.revoked_at.is_not(None), ApiKey.created_at.desc())
    ).all()
    return [ApiKeyRead(**_key_read(key, name)) for key, name in rows]


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_key(
    payload: ApiKeyCreate,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = MANAGE,
) -> ApiKeyCreated:
    _enabled(ctx)
    scopes = validate_scopes(payload.scopes, ctx.permissions)
    key, raw = create_api_key(
        db,
        workspace_id=ctx.workspace_id,
        actor_id=ctx.user_id,
        name=payload.name,
        scopes=scopes,
        expires_in_days=payload.expires_in_days,
    )
    audit(
        db,
        ctx.workspace_id,
        ctx.user_id,
        "api_key.created",
        "api_key",
        key.id,
        {"prefix": key.prefix, "scopes": scopes},
    )
    db.commit()
    user = db.get(User, ctx.user_id)
    return ApiKeyCreated(**_key_read(key, user.name if user else None), key=raw)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_key(
    key_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = MANAGE,
) -> None:
    key = db.scalar(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.workspace_id == ctx.workspace_id)
    )
    if key is None:
        raise NotFoundError("API key not found")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(UTC)
        audit(
            db,
            ctx.workspace_id,
            ctx.user_id,
            "api_key.revoked",
            "api_key",
            key.id,
            {"prefix": key.prefix},
        )
        db.commit()


# --- webhook endpoints -------------------------------------------------------------------------


def _get_endpoint(db: Session, ctx: WorkspaceContext, endpoint_id: int) -> WebhookEndpoint:
    endpoint = db.scalar(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id, WebhookEndpoint.workspace_id == ctx.workspace_id
        )
    )
    if endpoint is None:
        raise NotFoundError("Webhook endpoint not found")
    return endpoint


@router.get("/webhook-endpoints", response_model=list[EndpointRead])
def list_endpoints(
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = MANAGE,
) -> list[EndpointRead]:
    endpoints = db.scalars(
        select(WebhookEndpoint)
        .where(WebhookEndpoint.workspace_id == ctx.workspace_id)
        .order_by(WebhookEndpoint.created_at.desc())
    ).all()
    return [EndpointRead(**_endpoint_read(e)) for e in endpoints]


@router.post(
    "/webhook-endpoints", response_model=EndpointCreated, status_code=status.HTTP_201_CREATED
)
def create_endpoint(
    payload: EndpointWrite,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = MANAGE,
) -> EndpointCreated:
    _enabled(ctx)
    secret = new_secret()
    endpoint = WebhookEndpoint(
        workspace_id=ctx.workspace_id,
        url=validate_endpoint_url(payload.url or ""),
        description=payload.description,
        events=validate_events(payload.events or []),
        is_active=True,
        created_by_id=ctx.user_id,
    )
    set_secret(endpoint, secret)
    db.add(endpoint)
    db.flush()
    audit(
        db,
        ctx.workspace_id,
        ctx.user_id,
        "webhook_endpoint.created",
        "webhook_endpoint",
        endpoint.id,
        {"url": endpoint.url, "events": endpoint.events},
    )
    db.commit()
    db.refresh(endpoint)
    return EndpointCreated(**_endpoint_read(endpoint), secret=secret)


@router.patch("/webhook-endpoints/{endpoint_id}", response_model=EndpointRead)
def update_endpoint(
    endpoint_id: int,
    payload: EndpointWrite,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = MANAGE,
) -> EndpointRead:
    endpoint = _get_endpoint(db, ctx, endpoint_id)
    if payload.url is not None:
        endpoint.url = validate_endpoint_url(payload.url)
    if payload.description is not None:
        endpoint.description = payload.description
    if payload.events is not None:
        endpoint.events = validate_events(payload.events)
    if payload.is_active is not None:
        endpoint.is_active = payload.is_active
        if payload.is_active:
            endpoint.consecutive_failures = 0
            endpoint.disabled_reason = None
    audit(
        db,
        ctx.workspace_id,
        ctx.user_id,
        "webhook_endpoint.updated",
        "webhook_endpoint",
        endpoint.id,
        payload.model_dump(exclude_none=True),
    )
    db.commit()
    db.refresh(endpoint)
    return EndpointRead(**_endpoint_read(endpoint))


@router.delete("/webhook-endpoints/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_endpoint(
    endpoint_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = MANAGE,
) -> None:
    endpoint = _get_endpoint(db, ctx, endpoint_id)
    db.delete(endpoint)
    audit(
        db,
        ctx.workspace_id,
        ctx.user_id,
        "webhook_endpoint.deleted",
        "webhook_endpoint",
        endpoint_id,
        {"url": endpoint.url},
    )
    db.commit()


@router.post("/webhook-endpoints/{endpoint_id}/rotate-secret", response_model=SecretRead)
def rotate_secret(
    endpoint_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = MANAGE,
) -> SecretRead:
    endpoint = _get_endpoint(db, ctx, endpoint_id)
    secret = new_secret()
    set_secret(endpoint, secret)
    audit(
        db,
        ctx.workspace_id,
        ctx.user_id,
        "webhook_endpoint.secret_rotated",
        "webhook_endpoint",
        endpoint.id,
    )
    db.commit()
    return SecretRead(secret=secret)


@router.post("/webhook-endpoints/{endpoint_id}/test", response_model=DeliveryRead)
def test_endpoint(
    endpoint_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = MANAGE,
) -> DeliveryRead:
    endpoint = _get_endpoint(db, ctx, endpoint_id)
    delivery_id = send_test_event(db, endpoint)
    db.commit()
    return _delivery(db, delivery_id)


def _delivery(db: Session, delivery_id: int) -> DeliveryRead:
    delivery = db.get(WebhookDelivery, delivery_id)
    assert delivery is not None  # noqa: S101
    db.refresh(delivery)
    return DeliveryRead.model_validate(delivery, from_attributes=True)


@router.get("/webhook-endpoints/{endpoint_id}/deliveries", response_model=DeliveryPage)
def list_deliveries(
    endpoint_id: int,
    delivery_status: str | None = Query(default=None, alias="status", max_length=20),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = MANAGE,
) -> DeliveryPage:
    _get_endpoint(db, ctx, endpoint_id)
    conditions = [
        WebhookDelivery.endpoint_id == endpoint_id,
        WebhookDelivery.workspace_id == ctx.workspace_id,
    ]
    if delivery_status:
        conditions.append(WebhookDelivery.status == delivery_status)
    total = db.scalar(select(func.count(WebhookDelivery.id)).where(*conditions)) or 0
    rows = db.scalars(
        select(WebhookDelivery).where(*conditions).order_by(WebhookDelivery.id.desc()).limit(limit)
    ).all()
    return DeliveryPage(
        items=[DeliveryRead.model_validate(r, from_attributes=True) for r in rows], total=total
    )


@router.post("/webhook-deliveries/{delivery_id}/replay", response_model=DeliveryRead)
def replay_delivery(
    delivery_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = MANAGE,
) -> DeliveryRead:
    delivery = db.scalar(
        select(WebhookDelivery).where(
            WebhookDelivery.id == delivery_id, WebhookDelivery.workspace_id == ctx.workspace_id
        )
    )
    if delivery is None:
        raise NotFoundError("Delivery not found")
    new_id = replay(db, delivery)
    audit(
        db,
        ctx.workspace_id,
        ctx.user_id,
        "webhook_delivery.replayed",
        "webhook_delivery",
        delivery.id,
    )
    db.commit()
    return _delivery(db, new_id)
