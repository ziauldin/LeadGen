"""CRM integrations: connect HubSpot (OAuth) or Pipedrive (API token), sync settings and logs."""

from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace, require_permission
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError, ValidationFailedError
from app.core.flags import feature_enabled
from app.core.permissions import Permission
from app.core.tenancy import WorkspaceContext, system_session, workspace_scope
from app.models.integration import IntegrationConnection, IntegrationSyncLog
from app.models.workspace import Workspace
from app.services.billing.plans import features_for, require_feature
from app.services.integrations import clients
from app.services.integrations import service as integrations

router = APIRouter(tags=["integrations"])
logger = logging.getLogger(__name__)


class IntegrationProvider(BaseModel):
    key: str
    label: str
    auth: str  # oauth | token
    available: bool


class IntegrationSettings(BaseModel):
    push_contacts: bool
    push_deals: bool
    pull_status: bool


class IntegrationConnectionRead(BaseModel):
    id: int
    provider: str
    label: str
    status: str
    account_label: str | None
    settings: IntegrationSettings
    last_synced_at: datetime | None
    last_error: str | None
    created_at: datetime


class IntegrationsOverview(BaseModel):
    enabled: bool
    in_plan: bool
    providers: list[IntegrationProvider]
    connections: list[IntegrationConnectionRead]


class IntegrationConnectResponse(BaseModel):
    url: str


class PipedriveConnectRequest(BaseModel):
    api_token: str = Field(min_length=10, max_length=200)
    company_domain: str = Field(min_length=1, max_length=255)


class IntegrationSettingsUpdate(BaseModel):
    push_contacts: bool | None = None
    push_deals: bool | None = None
    pull_status: bool | None = None


class IntegrationSyncLogRead(BaseModel):
    id: int
    direction: str
    object_type: str
    local_id: int | None
    remote_id: str | None
    status: str
    message: str | None
    created_at: datetime


def _read(connection: IntegrationConnection) -> IntegrationConnectionRead:
    return IntegrationConnectionRead(
        id=connection.id,
        provider=connection.provider,
        label=integrations.PROVIDERS.get(connection.provider, {}).get("label", connection.provider),
        status=connection.status,
        account_label=connection.account_label,
        settings=IntegrationSettings(**integrations.settings_of(connection)),
        last_synced_at=connection.last_synced_at,
        last_error=connection.last_error,
        created_at=connection.created_at,
    )


def _enabled(ctx: WorkspaceContext = Depends(get_current_workspace)) -> WorkspaceContext:
    if not feature_enabled("integrations", ctx.workspace):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Integrations aren't enabled"
        )
    return ctx


def _in_plan(ctx: WorkspaceContext) -> None:
    require_feature(ctx.workspace, "integrations", "CRM integrations")


@router.get("/integrations", response_model=IntegrationsOverview)
def overview(
    ctx: WorkspaceContext = Depends(get_current_workspace), db: Session = Depends(get_db)
) -> IntegrationsOverview:
    enabled = feature_enabled("integrations", ctx.workspace)
    in_plan = features_for(ctx.workspace).integrations
    return IntegrationsOverview(
        enabled=enabled,
        in_plan=in_plan,
        providers=[
            IntegrationProvider(
                key=key,
                label=spec["label"],
                auth=spec["auth"],
                available=enabled and integrations.provider_available(key),
            )
            for key, spec in integrations.PROVIDERS.items()
        ],
        connections=[_read(c) for c in integrations.list_connections(db, ctx.workspace_id)]
        if enabled
        else [],
    )


@router.post("/integrations/hubspot/connect", response_model=IntegrationConnectResponse)
def connect_hubspot(
    ctx: WorkspaceContext = Depends(_enabled),
    _allowed: WorkspaceContext = Depends(
        require_permission(Permission.PROVIDERS_MANAGE, verified=True)
    ),
) -> IntegrationConnectResponse:
    _in_plan(ctx)
    if not clients.hubspot_configured():
        raise ValidationFailedError("HubSpot isn't set up on this server yet")
    return IntegrationConnectResponse(
        url=clients.hubspot_authorize_url(integrations.state_token(ctx.workspace_id, ctx.user_id))
    )


@router.get("/integrations/oauth/hubspot/callback", include_in_schema=False)
def hubspot_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """HubSpot sends the browser here after consent. Always lands back in the app."""

    def back(result: str, detail: str | None = None) -> RedirectResponse:
        query = urlencode({"integration": result, **({"detail": detail[:200]} if detail else {})})
        return RedirectResponse(
            f"{settings.frontend_url.rstrip('/')}/settings/integrations?{query}", status_code=302
        )

    if error or not code or not state:
        return back("cancelled", error)
    try:
        parsed = integrations.read_state(state)
        with system_session(db):
            workspace = db.get(Workspace, parsed.workspace_id)
        if workspace is None or not integrations.allowed(workspace):
            raise ValidationFailedError("CRM integrations aren't available for this workspace")
        tokens = clients.hubspot_exchange_code(code)
        with workspace_scope(db, parsed.workspace_id):
            integrations.connect(db, parsed.workspace_id, parsed.user_id, "hubspot", tokens)
    except (AppError, clients.IntegrationError) as exc:
        return back("error", str(exc))
    except Exception:
        logger.exception("HubSpot connection failed")
        return back("error", "Something went wrong. Please try again.")
    return back("connected")


@router.post("/integrations/pipedrive", response_model=IntegrationConnectionRead, status_code=201)
def connect_pipedrive(
    payload: PipedriveConnectRequest,
    ctx: WorkspaceContext = Depends(_enabled),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(
        require_permission(Permission.PROVIDERS_MANAGE, verified=True)
    ),
) -> IntegrationConnectionRead:
    _in_plan(ctx)
    connection = integrations.connect(
        db,
        ctx.workspace_id,
        ctx.user_id,
        "pipedrive",
        {"api_token": payload.api_token.strip(), "company_domain": payload.company_domain},
    )
    return _read(connection)


@router.patch("/integrations/{connection_id}", response_model=IntegrationConnectionRead)
def update_integration(
    connection_id: int,
    payload: IntegrationSettingsUpdate,
    ctx: WorkspaceContext = Depends(_enabled),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.PROVIDERS_MANAGE)),
) -> IntegrationConnectionRead:
    connection = integrations.get_connection(db, ctx.workspace_id, connection_id)
    changes = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    return _read(integrations.update_settings(db, connection, ctx.user_id, changes))


@router.delete("/integrations/{connection_id}", status_code=204)
def delete_integration(
    connection_id: int,
    ctx: WorkspaceContext = Depends(_enabled),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.PROVIDERS_MANAGE)),
) -> Response:
    integrations.disconnect(
        db, integrations.get_connection(db, ctx.workspace_id, connection_id), ctx.user_id
    )
    return Response(status_code=204)


@router.post("/integrations/{connection_id}/sync", status_code=202)
def sync_now(
    connection_id: int,
    ctx: WorkspaceContext = Depends(_enabled),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.PROVIDERS_MANAGE)),
) -> dict[str, bool]:
    """Push interested leads and all deals, then pull deal status, in the background."""
    _in_plan(ctx)
    connection = integrations.get_connection(db, ctx.workspace_id, connection_id)
    if connection.status != "active":
        raise ValidationFailedError("Reconnect this integration before syncing")
    from app.workers.integration_jobs import sync_integration_all

    sync_integration_all.delay(connection.id)
    return {"queued": True}


@router.get("/integrations/{connection_id}/logs", response_model=list[IntegrationSyncLogRead])
def sync_logs(
    connection_id: int,
    ctx: WorkspaceContext = Depends(_enabled),
    db: Session = Depends(get_db),
) -> list[IntegrationSyncLog]:
    connection = integrations.get_connection(db, ctx.workspace_id, connection_id)
    return integrations.recent_logs(db, connection)
