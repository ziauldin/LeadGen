"""Connect Gmail / Microsoft 365 mailboxes, see their health, and set campaign sender pools."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace, require_permission
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError, NotFoundError
from app.core.flags import feature_enabled
from app.core.permissions import Permission
from app.core.tenancy import WorkspaceContext, workspace_scope
from app.models.campaign import Campaign
from app.models.enums import ProviderType
from app.models.provider_credential import ProviderCredential
from app.services.mailboxes import oauth
from app.services.mailboxes.service import (
    MAILBOX_PROVIDERS,
    complete_connection,
    effective_cap,
    pool,
    set_campaign_senders,
    usable,
)
from app.services.provider_credentials.service import _as_str
from app.services.workspaces.service import audit

router = APIRouter(tags=["mailboxes"])
logger = logging.getLogger(__name__)


class ConnectResponse(BaseModel):
    url: str


class MailboxProvider(BaseModel):
    key: str
    label: str
    available: bool


class SenderAccount(BaseModel):
    id: int
    provider: str
    label: str
    email: str | None
    daily_limit: int | None
    cap_today: int | None
    healthy: bool
    problem: str | None
    is_mailbox: bool


class MailboxUpdate(BaseModel):
    daily_limit: int | None = Field(default=None, ge=1, le=2000)
    resume: bool = False


class SendersUpdate(BaseModel):
    credential_ids: list[int] = Field(default_factory=list, max_length=50)


def _enabled(ctx: WorkspaceContext) -> None:
    if not feature_enabled("mailbox_oauth", ctx.workspace):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox connections aren't enabled"
        )


def _account(credential: ProviderCredential) -> SenderAccount:
    name = _as_str(credential.provider_name)
    summary = credential.masked_summary or credential.display_name
    email = credential.display_name if "@" in (credential.display_name or "") else None
    return SenderAccount(
        id=credential.id,
        provider=name,
        label=summary,
        email=email,
        daily_limit=credential.daily_limit,
        cap_today=effective_cap(credential, datetime.now(UTC)),
        healthy=usable(credential),
        problem=credential.disabled_reason,
        is_mailbox=name in MAILBOX_PROVIDERS,
    )


@router.get("/mailboxes/providers", response_model=list[MailboxProvider])
def mailbox_providers(
    ctx: WorkspaceContext = Depends(get_current_workspace),
) -> list[MailboxProvider]:
    on = feature_enabled("mailbox_oauth", ctx.workspace)
    return [
        MailboxProvider(key=k, label=p.label, available=on and p.configured)
        for k, p in oauth.PROVIDERS.items()
    ]


@router.post("/mailboxes/{provider}/connect", response_model=ConnectResponse)
def connect_mailbox(
    provider: str,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    _allowed: WorkspaceContext = Depends(
        require_permission(Permission.PROVIDERS_MANAGE, verified=True)
    ),
) -> ConnectResponse:
    _enabled(ctx)
    return ConnectResponse(
        url=oauth.authorization_url(provider, workspace_id=ctx.workspace_id, user_id=ctx.user_id)
    )


@router.get("/mailboxes/oauth/{provider}/callback", include_in_schema=False)
def mailbox_callback(
    provider: str,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """The provider sends the browser here after consent. Always lands back in the app."""

    def back(result: str, detail: str | None = None) -> RedirectResponse:
        query = urlencode({"mailbox": result, **({"detail": detail[:200]} if detail else {})})
        return RedirectResponse(
            f"{settings.frontend_url.rstrip('/')}/settings/providers?{query}", status_code=302
        )

    if error or not code or not state:
        return back("cancelled", error)
    try:
        parsed = oauth.read_state(state, provider)
        with workspace_scope(db, parsed.workspace_id):
            complete_connection(db, parsed, code)
    except (AppError, oauth.MailboxAuthError) as exc:
        return back("error", str(exc))
    except Exception:
        logger.exception("Mailbox connection failed")
        return back("error", "Something went wrong. Please try again.")
    return back("connected")


@router.get("/sending-accounts", response_model=list[SenderAccount])
def sending_accounts(
    ctx: WorkspaceContext = Depends(get_current_workspace), db: Session = Depends(get_db)
) -> list[SenderAccount]:
    """Every email-sending account in the workspace, with today's cap and health."""
    rows = db.scalars(
        select(ProviderCredential)
        .where(
            ProviderCredential.workspace_id == ctx.workspace_id,
            ProviderCredential.provider_type == ProviderType.EMAIL,
        )
        .order_by(ProviderCredential.id)
    ).all()
    return [_account(c) for c in rows if _as_str(c.provider_name) != "mock" or len(rows) == 1]


@router.patch("/sending-accounts/{credential_id}", response_model=SenderAccount)
def update_sending_account(
    credential_id: int,
    payload: MailboxUpdate,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.PROVIDERS_MANAGE)),
) -> SenderAccount:
    credential = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.id == credential_id,
            ProviderCredential.workspace_id == ctx.workspace_id,
            ProviderCredential.provider_type == ProviderType.EMAIL,
        )
    )
    if credential is None:
        raise NotFoundError("Sending account not found")
    if "daily_limit" in payload.model_fields_set:
        credential.daily_limit = payload.daily_limit
    if (
        payload.resume
        and credential.disabled_at
        and not (credential.disabled_reason or "").startswith("Reconnect")
    ):
        credential.disabled_at = None
        credential.disabled_reason = None
    audit(
        db,
        ctx.workspace_id,
        ctx.user_id,
        "sending_account_updated",
        "provider_credential",
        credential.id,
        payload.model_dump(exclude_unset=True),
    )
    db.commit()
    return _account(credential)


def _campaign(db: Session, ctx: WorkspaceContext, campaign_id: int) -> Campaign:
    campaign = db.scalar(
        select(Campaign).where(
            Campaign.id == campaign_id, Campaign.workspace_id == ctx.workspace_id
        )
    )
    if campaign is None:
        raise NotFoundError("Campaign not found")
    return campaign


@router.get("/campaigns/{campaign_id}/senders", response_model=list[SenderAccount])
def campaign_senders(
    campaign_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[SenderAccount]:
    return [_account(c) for c in pool(db, _campaign(db, ctx, campaign_id))]


@router.put("/campaigns/{campaign_id}/senders", response_model=list[SenderAccount])
def update_campaign_senders(
    campaign_id: int,
    payload: SendersUpdate,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.CAMPAIGNS_MANAGE)),
) -> list[SenderAccount]:
    campaign = _campaign(db, ctx, campaign_id)
    credentials = set_campaign_senders(db, campaign, payload.credential_ids)
    audit(
        db,
        ctx.workspace_id,
        ctx.user_id,
        "campaign_senders_updated",
        "campaign",
        campaign.id,
        {"credential_ids": payload.credential_ids},
    )
    db.commit()
    return [_account(c) for c in credentials]
