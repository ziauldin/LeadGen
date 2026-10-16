"""Single sign-on: Google, Microsoft and workspace identity providers (OIDC and SAML)."""

from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Depends, Form, Query, Request, status
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_workspace, require_permission
from app.api.routes.auth import _set_refresh_cookie
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import NotFoundError, ValidationFailedError
from app.core.permissions import Permission
from app.core.rate_limit import client_ip, enforce, limiter
from app.core.tenancy import WorkspaceContext
from app.models.audit_log import AuditLog
from app.models.sso import ExternalIdentity, SsoConnection, VerifiedDomain
from app.models.user import User
from app.services.auth import mfa, tokens
from app.services.sso import oidc, saml
from app.services.sso import service as sso
from app.services.sso.http import SsoError

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sso"])
STATE_COOKIE = "lg_sso"


# --- schemas -------------------------------------------------------------------------------------


class ProvidersRead(BaseModel):
    google: bool
    microsoft: bool
    sso: bool


class UrlRead(BaseModel):
    url: str


class DiscoverRequest(BaseModel):
    email: EmailStr


class DiscoverRead(BaseModel):
    url: str
    display_name: str


class IdentityRead(BaseModel):
    id: int
    provider: str
    email: str | None
    created_at: str
    last_used_at: str | None


class DomainRead(BaseModel):
    id: int
    domain: str
    verified: bool
    txt_record: str


class DomainCreate(BaseModel):
    domain: str = Field(min_length=3, max_length=255)


class ConnectionRead(BaseModel):
    id: int
    protocol: str
    display_name: str
    is_active: bool
    enforce: bool
    default_role: str
    oidc_issuer: str | None
    oidc_client_id: str | None
    has_client_secret: bool
    saml_idp_entity_id: str | None
    saml_idp_sso_url: str | None
    has_certificate: bool
    sp_entity_id: str
    acs_url: str
    oidc_redirect_uri: str
    last_login_at: str | None


class ConnectionWrite(BaseModel):
    protocol: str | None = Field(default=None, pattern="^(oidc|saml)$")
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None
    enforce: bool | None = None
    default_role: str | None = Field(default=None, pattern="^(member|admin)$")
    oidc_issuer: str | None = Field(default=None, max_length=500)
    oidc_client_id: str | None = Field(default=None, max_length=255)
    oidc_client_secret: str | None = Field(default=None, max_length=1000)
    saml_idp_entity_id: str | None = Field(default=None, max_length=500)
    saml_idp_sso_url: str | None = Field(default=None, max_length=1000)
    saml_idp_certificate: str | None = Field(default=None, max_length=20_000)


# --- helpers -------------------------------------------------------------------------------------


def _frontend(path: str, **params: str | None) -> str:
    query = urlencode({k: v for k, v in params.items() if v})
    return f"{settings.frontend_url.rstrip('/')}{path}{'?' + query if query else ''}"


def _fail(message: str) -> RedirectResponse:
    return RedirectResponse(
        _frontend("/login", error=message), status_code=status.HTTP_303_SEE_OTHER
    )


def _finish(
    request: Request,
    db: Session,
    user: User,
    next_path: str | None,
    *,
    via: str,
    require_mfa: bool = True,
) -> RedirectResponse:
    db.add(
        AuditLog(
            actor_id=user.id,
            action="login_sso",
            entity_type="user",
            entity_id=user.id,
            metadata_={"via": via},
        )
    )
    db.commit()
    if require_mfa and user.mfa_enabled:
        return RedirectResponse(
            _frontend("/login", mfa_token=mfa.issue_mfa_token(user), next=next_path),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    raw, _ = tokens.issue_refresh_token(
        db, user, ip=client_ip(request), user_agent=request.headers.get("user-agent")
    )
    db.commit()
    response = RedirectResponse(
        _frontend("/auth/complete", next=next_path), status_code=status.HTTP_303_SEE_OTHER
    )
    _set_refresh_cookie(response, raw)
    response.delete_cookie(STATE_COOKIE, path=settings.refresh_cookie_path)
    return response


def _bind_browser(response: RedirectResponse, state_id: str) -> RedirectResponse:
    """Tie the sign-in to this browser so a forged callback can't log someone in."""
    response.set_cookie(
        STATE_COOKIE,
        state_id,
        max_age=int(sso.STATE_TTL.total_seconds()),
        path=settings.refresh_cookie_path,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return response


def _social_client(provider: str) -> oidc.OidcClient:
    client = sso.social_client(provider)
    if client is None:
        raise NotFoundError("This sign-in method isn't available")
    return client


# --- public sign-in ------------------------------------------------------------------------------


@router.get("/auth/providers", response_model=ProvidersRead)
def sign_in_providers() -> ProvidersRead:
    enabled = sso.enabled_social_providers()
    return ProvidersRead(
        google="google" in enabled, microsoft="microsoft" in enabled, sso=settings.feature_sso
    )


def _start_social(
    db: Session, provider: str, next_path: str | None, link_user_id: int | None
) -> RedirectResponse:
    client = _social_client(provider)
    verifier, challenge = oidc.pkce_pair()
    state = sso.create_state(
        db,
        provider=provider,
        next_path=next_path,
        link_user_id=link_user_id,
        code_verifier=verifier,
    )
    url = oidc.authorization_url(
        client,
        redirect_uri=sso.oidc_callback_url(provider=provider),
        state=state.id,
        nonce=state.nonce,
        code_challenge=challenge,
    )
    return _bind_browser(RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER), state.id)


@router.get("/auth/oidc/{provider}/start", include_in_schema=False)
@limiter.limit("30/minute")
def social_start(
    request: Request,
    provider: str,
    next: str | None = Query(default=None, max_length=500),
    db: Session = Depends(get_db),
) -> Response:
    try:
        return _start_social(db, provider, next, None)
    except SsoError as exc:
        return _fail(str(exc))


@router.post("/auth/oidc/{provider}/link", response_model=UrlRead)
def social_link_start(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UrlRead:
    """Start connecting Google/Microsoft to the signed-in account. Returns where to go next."""
    _social_client(provider)
    verifier, _challenge = oidc.pkce_pair()
    state = sso.create_state(
        db,
        provider=provider,
        next_path="/settings/security",
        link_user_id=current_user.id,
        code_verifier=verifier,
    )
    return UrlRead(url=sso.public_url(f"/auth/oidc/{provider}/resume?state={state.id}"))


@router.get("/auth/oidc/{provider}/resume", include_in_schema=False)
def social_link_resume(provider: str, state: str, db: Session = Depends(get_db)) -> Response:
    """Second half of linking: bind the browser and send it to the provider."""
    try:
        client = _social_client(provider)
        record = db.get(sso.SsoLoginState, state)
        if record is None or record.used_at is not None or record.provider != provider:
            raise SsoError("This link has expired. Please try again.")
        verifier, challenge = oidc.pkce_pair()
        record.code_verifier = verifier
        db.commit()
        url = oidc.authorization_url(
            client,
            redirect_uri=sso.oidc_callback_url(provider=provider),
            state=record.id,
            nonce=record.nonce,
            code_challenge=challenge,
        )
    except SsoError as exc:
        return _fail(str(exc))
    return _bind_browser(RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER), state)


@router.get("/auth/oidc/{provider}/callback", include_in_schema=False)
def social_callback(
    request: Request,
    provider: str,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    bound_state: str | None = Cookie(default=None, alias=STATE_COOKIE),
    db: Session = Depends(get_db),
) -> Response:
    if error:
        return _fail("Sign-in was cancelled")
    try:
        client = _social_client(provider)
        if not state or not bound_state or not secrets.compare_digest(state, bound_state):
            raise SsoError("The sign-in didn't start in this browser. Please try again.")
        record = sso.consume_state(db, state, provider=provider)
        claims = oidc.exchange_code(
            client,
            code=code or "",
            redirect_uri=sso.oidc_callback_url(provider=provider),
            code_verifier=record.code_verifier or "",
            nonce=record.nonce,
        )
        user, _created = sso.complete_social_login(db, provider, claims, record)
        if record.link_user_id is not None:
            response = RedirectResponse(
                _frontend("/settings/security", linked=provider),
                status_code=status.HTTP_303_SEE_OTHER,
            )
            response.delete_cookie(STATE_COOKIE, path=settings.refresh_cookie_path)
            return response
        blocked = sso.password_login_blocked(db, user)
        if blocked is not None:
            raise SsoError(f"Your organisation requires signing in with {blocked.display_name}.")
        return _finish(request, db, user, record.next_path, via=provider)
    except SsoError as exc:
        return _fail(str(exc))


@router.post("/auth/sso/discover", response_model=DiscoverRead)
@limiter.limit("20/minute")
def sso_discover(
    request: Request, payload: DiscoverRequest, db: Session = Depends(get_db)
) -> DiscoverRead:
    """Find the workspace identity provider for an email address."""
    enforce("10/minute", "sso-discover", client_ip(request) or "unknown")
    connection = sso.connection_for_email(db, str(payload.email))
    if connection is None:
        raise NotFoundError("Single sign-on isn't set up for that email domain")
    query = urlencode({"login_hint": str(payload.email)})
    return DiscoverRead(
        url=sso.public_url(f"/auth/sso/{connection.id}/start?{query}"),
        display_name=connection.display_name,
    )


@router.get("/auth/sso/{connection_id}/start", include_in_schema=False)
def sso_start(
    connection_id: int,
    next: str | None = Query(default=None, max_length=500),
    login_hint: str | None = Query(default=None, max_length=255),
    db: Session = Depends(get_db),
) -> Response:
    try:
        connection = sso.get_connection_public(db, connection_id)
        if connection.protocol == "saml":
            state = sso.create_state(
                db, provider="saml", connection_id=connection.id, next_path=next
            )
            url = saml.authn_request_url(
                idp_sso_url=connection.saml_idp_sso_url or "",
                sp_entity_id=sso.sp_entity_id(connection),
                acs_url=sso.acs_url(connection),
                request_id=f"_{state.nonce}",
                relay_state=state.id,
            )
            return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)
        verifier, challenge = oidc.pkce_pair()
        state = sso.create_state(
            db, provider="oidc", connection_id=connection.id, next_path=next, code_verifier=verifier
        )
        url = oidc.authorization_url(
            sso.connection_client(connection),
            redirect_uri=sso.oidc_callback_url(connection),
            state=state.id,
            nonce=state.nonce,
            code_challenge=challenge,
            login_hint=login_hint,
        )
        return _bind_browser(RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER), state.id)
    except SsoError as exc:
        return _fail(str(exc))


@router.get("/auth/sso/{connection_id}/callback", include_in_schema=False)
def sso_oidc_callback(
    request: Request,
    connection_id: int,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    bound_state: str | None = Cookie(default=None, alias=STATE_COOKIE),
    db: Session = Depends(get_db),
) -> Response:
    if error:
        return _fail("Sign-in was cancelled")
    try:
        connection = sso.get_connection_public(db, connection_id)
        if not state or not bound_state or not secrets.compare_digest(state, bound_state):
            raise SsoError("The sign-in didn't start in this browser. Please try again.")
        record = sso.consume_state(db, state, provider="oidc")
        if record.connection_id != connection.id:
            raise SsoError("This sign-in link doesn't belong to that connection")
        claims = oidc.exchange_code(
            sso.connection_client(connection),
            code=code or "",
            redirect_uri=sso.oidc_callback_url(connection),
            code_verifier=record.code_verifier or "",
            nonce=record.nonce,
        )
        user = sso.complete_enterprise_login(
            db, connection, email=claims.email, subject=claims.subject, name=claims.name
        )
        return _finish(
            request, db, user, record.next_path, via=f"sso:{connection.id}", require_mfa=False
        )
    except SsoError as exc:
        return _fail(str(exc))


@router.post("/auth/saml/{connection_id}/acs", include_in_schema=False)
def saml_acs(
    request: Request,
    connection_id: int,
    saml_response: str = Form(alias="SAMLResponse", max_length=500_000),
    relay_state: str = Form(alias="RelayState", max_length=200),
    db: Session = Depends(get_db),
) -> Response:
    try:
        connection = sso.get_connection_public(db, connection_id)
        record = sso.consume_state(db, relay_state, provider="saml")
        if record.connection_id != connection.id:
            raise SsoError("This sign-in doesn't belong to that connection")
        identity = saml.parse_response(
            saml_response,
            idp_entity_id=connection.saml_idp_entity_id or "",
            idp_certificate=connection.saml_idp_certificate or "",
            sp_entity_id=sso.sp_entity_id(connection),
            acs_url=sso.acs_url(connection),
            expected_request_id=f"_{record.nonce}",
        )
        user = sso.complete_enterprise_login(
            db, connection, email=identity.email, subject=identity.subject, name=identity.name
        )
        return _finish(
            request, db, user, record.next_path, via=f"sso:{connection.id}", require_mfa=False
        )
    except SsoError as exc:
        return _fail(str(exc))


@router.get("/auth/saml/{connection_id}/metadata", include_in_schema=False)
def saml_metadata(connection_id: int, db: Session = Depends(get_db)) -> Response:
    try:
        connection = sso.get_connection_public(db, connection_id)
    except SsoError as exc:
        raise NotFoundError(str(exc)) from exc
    xml = saml.sp_metadata(
        sp_entity_id=sso.sp_entity_id(connection), acs_url=sso.acs_url(connection)
    )
    return Response(content=xml, media_type="application/samlmetadata+xml")


# --- linked identities (signed-in user) ---------------------------------------------------------


@router.get("/auth/identities", response_model=list[IdentityRead])
def list_identities(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[IdentityRead]:
    rows = db.scalars(
        select(ExternalIdentity)
        .where(ExternalIdentity.user_id == current_user.id)
        .order_by(ExternalIdentity.id)
    ).all()
    return [
        IdentityRead(
            id=row.id,
            provider=row.provider,
            email=row.email,
            created_at=row.created_at.isoformat(),
            last_used_at=row.last_used_at.isoformat() if row.last_used_at else None,
        )
        for row in rows
    ]


@router.delete("/auth/identities/{identity_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_identity(
    identity_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    row = db.scalar(
        select(ExternalIdentity).where(
            ExternalIdentity.id == identity_id, ExternalIdentity.user_id == current_user.id
        )
    )
    if row is None:
        raise NotFoundError("Not found")
    db.delete(row)
    db.add(
        AuditLog(
            actor_id=current_user.id,
            action="identity_unlinked",
            entity_type="user",
            entity_id=current_user.id,
            metadata_={"provider": row.provider},
        )
    )
    db.commit()


# --- workspace administration -------------------------------------------------------------------


def _domain_read(record: VerifiedDomain) -> DomainRead:
    return DomainRead(
        id=record.id,
        domain=record.domain,
        verified=record.verified_at is not None,
        txt_record=sso.verification_record(record),
    )


def _connection_read(connection: SsoConnection) -> ConnectionRead:
    return ConnectionRead(
        id=connection.id,
        protocol=connection.protocol,
        display_name=connection.display_name,
        is_active=connection.is_active,
        enforce=connection.enforce,
        default_role=connection.default_role,
        oidc_issuer=connection.oidc_issuer,
        oidc_client_id=connection.oidc_client_id,
        has_client_secret=bool(connection.oidc_client_secret_encrypted),
        saml_idp_entity_id=connection.saml_idp_entity_id,
        saml_idp_sso_url=connection.saml_idp_sso_url,
        has_certificate=bool(connection.saml_idp_certificate),
        sp_entity_id=sso.sp_entity_id(connection),
        acs_url=sso.acs_url(connection),
        oidc_redirect_uri=sso.oidc_callback_url(connection),
        last_login_at=connection.last_login_at.isoformat() if connection.last_login_at else None,
    )


@router.get("/sso/domains", response_model=list[DomainRead])
def list_domains(
    ctx: WorkspaceContext = Depends(get_current_workspace), db: Session = Depends(get_db)
) -> list[DomainRead]:
    rows = db.scalars(
        select(VerifiedDomain)
        .where(VerifiedDomain.workspace_id == ctx.workspace_id)
        .order_by(VerifiedDomain.domain)
    ).all()
    return [_domain_read(row) for row in rows]


@router.post("/sso/domains", response_model=DomainRead, status_code=status.HTTP_201_CREATED)
def add_domain(
    payload: DomainCreate,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.SSO_MANAGE)),
) -> DomainRead:
    return _domain_read(sso.add_domain(db, ctx.workspace_id, payload.domain))


@router.post("/sso/domains/{domain_id}/verify", response_model=DomainRead)
def verify_domain(
    domain_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.SSO_MANAGE)),
) -> DomainRead:
    enforce("10/minute", "verify-domain", str(ctx.workspace_id))
    return _domain_read(sso.verify_domain(db, ctx.workspace_id, domain_id))


@router.delete("/sso/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_domain(
    domain_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.SSO_MANAGE)),
) -> None:
    row = db.scalar(
        select(VerifiedDomain).where(
            VerifiedDomain.id == domain_id, VerifiedDomain.workspace_id == ctx.workspace_id
        )
    )
    if row is None:
        raise NotFoundError("Domain not found")
    db.delete(row)
    db.commit()


@router.get("/sso/connections", response_model=list[ConnectionRead])
def list_connections(
    ctx: WorkspaceContext = Depends(get_current_workspace), db: Session = Depends(get_db)
) -> list[ConnectionRead]:
    rows = db.scalars(
        select(SsoConnection)
        .where(SsoConnection.workspace_id == ctx.workspace_id)
        .order_by(SsoConnection.id)
    ).all()
    return [_connection_read(row) for row in rows]


@router.post("/sso/connections", response_model=ConnectionRead, status_code=status.HTTP_201_CREATED)
def create_connection(
    payload: ConnectionWrite,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.SSO_MANAGE)),
) -> ConnectionRead:
    if not payload.protocol or not payload.display_name:
        raise ValidationFailedError("Choose a protocol and give the connection a name")
    return _connection_read(
        sso.save_connection(db, ctx.workspace, payload.model_dump(exclude_unset=True))
    )


@router.patch("/sso/connections/{connection_id}", response_model=ConnectionRead)
def update_connection(
    connection_id: int,
    payload: ConnectionWrite,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.SSO_MANAGE)),
) -> ConnectionRead:
    row = db.scalar(
        select(SsoConnection).where(
            SsoConnection.id == connection_id, SsoConnection.workspace_id == ctx.workspace_id
        )
    )
    if row is None:
        raise NotFoundError("Connection not found")
    return _connection_read(
        sso.save_connection(db, ctx.workspace, payload.model_dump(exclude_unset=True), row)
    )


@router.delete("/sso/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    connection_id: int,
    ctx: WorkspaceContext = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    _allowed: WorkspaceContext = Depends(require_permission(Permission.SSO_MANAGE)),
) -> None:
    row = db.scalar(
        select(SsoConnection).where(
            SsoConnection.id == connection_id, SsoConnection.workspace_id == ctx.workspace_id
        )
    )
    if row is None:
        raise NotFoundError("Connection not found")
    db.delete(row)
    db.commit()
