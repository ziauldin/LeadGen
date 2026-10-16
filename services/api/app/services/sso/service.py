"""Sign-in with Google, Microsoft and workspace identity providers.

Account matching rules:

* An identity already linked to a user signs that user in.
* Google: a verified Google email signs in (and links) the account with that email.
* Microsoft: emails in Microsoft tokens aren't always verified (the "nOAuth" problem), so a
  Microsoft identity never takes over an existing account by email. Users link it from
  Settings while signed in instead.
* Workspace IdPs: only for email domains the workspace has proved it owns. Users are created
  or added to the workspace on first sign-in (just-in-time provisioning).
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.core.flags import feature_enabled
from app.core.security import decrypt_secret_payload, encrypt_secret_payload, get_password_hash
from app.core.tenancy import bind_session, system_session
from app.models.audit_log import AuditLog
from app.models.sso import ExternalIdentity, SsoConnection, SsoLoginState, VerifiedDomain
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.services.billing.plans import features_for
from app.services.compliance.freemail import is_freemail_domain
from app.services.sso.http import SsoError
from app.services.sso.oidc import IdTokenClaims, OidcClient

STATE_TTL = timedelta(minutes=10)
SOCIAL_PROVIDERS = ("google", "microsoft")
VERIFICATION_PREFIX = "leadsgen-verification="


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


# --- configuration ------------------------------------------------------------------------------


def social_client(provider: str) -> OidcClient | None:
    if provider == "google" and settings.google_oauth_client_id:
        return OidcClient(
            issuer="https://accounts.google.com",
            client_id=settings.google_oauth_client_id,
            client_secret=settings.google_oauth_client_secret,
        )
    if provider == "microsoft" and settings.microsoft_oauth_client_id:
        return OidcClient(
            issuer="https://login.microsoftonline.com/common/v2.0",
            client_id=settings.microsoft_oauth_client_id,
            client_secret=settings.microsoft_oauth_client_secret,
            multi_tenant_issuer=True,
        )
    return None


def enabled_social_providers() -> list[str]:
    return [p for p in SOCIAL_PROVIDERS if social_client(p) is not None]


def public_url(path: str) -> str:
    """Browser-facing URL for an API path (through the web app's /api proxy)."""
    return f"{settings.frontend_url.rstrip('/')}/api{path}"


def sp_entity_id(connection: SsoConnection) -> str:
    return public_url(f"/auth/saml/{connection.id}/metadata")


def acs_url(connection: SsoConnection) -> str:
    return public_url(f"/auth/saml/{connection.id}/acs")


def oidc_callback_url(connection: SsoConnection | None = None, provider: str | None = None) -> str:
    if connection is not None:
        return public_url(f"/auth/sso/{connection.id}/callback")
    return public_url(f"/auth/oidc/{provider}/callback")


def connection_client(connection: SsoConnection) -> OidcClient:
    if not (connection.oidc_issuer and connection.oidc_client_id):
        raise SsoError("This identity provider isn't fully set up")
    secret = (
        decrypt_secret_payload(connection.oidc_client_secret_encrypted)
        if connection.oidc_client_secret_encrypted
        else ""
    )
    return OidcClient(
        issuer=connection.oidc_issuer, client_id=connection.oidc_client_id, client_secret=secret
    )


# --- login state ----------------------------------------------------------------------------


def create_state(
    db: Session,
    *,
    provider: str,
    connection_id: int | None = None,
    next_path: str | None = None,
    link_user_id: int | None = None,
    code_verifier: str | None = None,
) -> SsoLoginState:
    state = SsoLoginState(
        id=secrets.token_urlsafe(32),
        provider=provider,
        connection_id=connection_id,
        nonce=secrets.token_urlsafe(24),
        code_verifier=code_verifier,
        next_path=next_path
        if next_path and next_path.startswith("/") and not next_path.startswith("//")
        else None,
        link_user_id=link_user_id,
        expires_at=_now() + STATE_TTL,
    )
    db.add(state)
    db.commit()
    return state


def consume_state(db: Session, state_id: str | None, *, provider: str) -> SsoLoginState:
    state = db.get(SsoLoginState, state_id) if state_id else None
    if (
        state is None
        or state.provider != provider
        or state.used_at is not None
        or _aware(state.expires_at) <= _now()
    ):
        raise SsoError("This sign-in link has expired or was already used. Please try again.")
    state.used_at = _now()
    db.commit()
    return state


# --- users -----------------------------------------------------------------------------------


def _audit(db: Session, user: User, action: str, metadata: dict | None = None) -> None:
    db.add(
        AuditLog(
            actor_id=user.id,
            action=action,
            entity_type="user",
            entity_id=user.id,
            metadata_=metadata,
        )
    )


def _identity(db: Session, provider: str, subject: str) -> ExternalIdentity | None:
    return db.scalar(
        select(ExternalIdentity).where(
            ExternalIdentity.provider == provider, ExternalIdentity.subject == subject
        )
    )


def _link(db: Session, user: User, provider: str, subject: str, email: str) -> ExternalIdentity:
    identity = ExternalIdentity(user_id=user.id, provider=provider, subject=subject, email=email)
    db.add(identity)
    _audit(db, user, "identity_linked", {"provider": provider})
    return identity


def _new_user(db: Session, *, email: str, name: str | None, verified: bool) -> User:
    user = User(
        name=(name or email.split("@")[0])[:255],
        email=email,
        hashed_password=get_password_hash(secrets.token_urlsafe(32)),  # no usable password
        email_verified_at=_now() if verified else None,
    )
    db.add(user)
    db.flush()
    _audit(db, user, "user_registered", {"via": "sso"})
    return user


def complete_social_login(
    db: Session, provider: str, claims: IdTokenClaims, state: SsoLoginState
) -> tuple[User, bool]:
    """Find or create the user for a Google/Microsoft sign-in. Returns (user, created)."""
    from app.services.workspaces.service import create_personal_workspace

    identity = _identity(db, provider, claims.subject)
    if state.link_user_id is not None:
        user = db.get(User, state.link_user_id)
        if user is None:
            raise SsoError("Your session ended. Sign in and try connecting again.")
        if identity is not None and identity.user_id != user.id:
            raise SsoError("That account is already connected to a different LeadsGen user.")
        if identity is None:
            _link(db, user, provider, claims.subject, claims.email)
        db.commit()
        return user, False

    if identity is not None:
        user = db.get(User, identity.user_id)
        if user is None or not user.is_active:
            raise SsoError("This account is disabled")
        identity.last_used_at = _now()
        db.commit()
        return user, False

    existing = db.scalar(select(User).where(User.email == claims.email))
    if existing is not None:
        if provider == "google" and claims.email_verified:
            _link(db, existing, provider, claims.subject, claims.email)
            if existing.email_verified_at is None:
                existing.email_verified_at = _now()
            db.commit()
            return existing, False
        raise SsoError(
            "An account with this email already exists. Sign in with your password, then "
            "connect this sign-in method from Settings → Security."
        )

    user = _new_user(
        db,
        email=claims.email,
        name=claims.name,
        verified=provider == "google" and claims.email_verified,
    )
    _link(db, user, provider, claims.subject, claims.email)
    db.commit()
    create_personal_workspace(db, user)
    return user, True


def complete_enterprise_login(
    db: Session,
    connection: SsoConnection,
    *,
    email: str,
    subject: str,
    name: str | None,
) -> User:
    """Sign in through a workspace IdP, creating the user and membership if needed."""
    domain = email.rsplit("@", 1)[-1]
    with system_session(db):
        verified = db.scalar(
            select(VerifiedDomain.id).where(
                VerifiedDomain.workspace_id == connection.workspace_id,
                VerifiedDomain.domain == domain,
                VerifiedDomain.verified_at.is_not(None),
            )
        )
    if verified is None:
        raise SsoError(f"{domain} isn't a verified domain for this workspace")

    provider = f"sso:{connection.id}"
    identity = _identity(db, provider, subject)
    user = db.get(User, identity.user_id) if identity else None
    if user is None:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = _new_user(db, email=email, name=name, verified=True)
        _link(db, user, provider, subject, email)
    elif identity is not None:
        identity.last_used_at = _now()
    if not user.is_active:
        raise SsoError("This account is disabled")
    if user.email_verified_at is None:
        user.email_verified_at = _now()

    membership = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == connection.workspace_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if membership is None:
        role = (
            connection.default_role if connection.default_role in ("member", "admin") else "member"
        )
        db.add(WorkspaceMember(workspace_id=connection.workspace_id, user_id=user.id, role=role))
        _audit(db, user, "sso_provisioned", {"workspace_id": connection.workspace_id})
    user.last_workspace_id = connection.workspace_id
    connection.last_login_at = _now()
    db.commit()
    return user


# --- discovery and enforcement --------------------------------------------------------------


def _usable(db: Session, connection: SsoConnection) -> bool:
    workspace = db.get(Workspace, connection.workspace_id)
    if workspace is None or not connection.is_active or not feature_enabled("sso", workspace):
        return False
    features = features_for(workspace)
    return features.saml if connection.protocol == "saml" else features.sso


def connection_for_email(db: Session, email: str) -> SsoConnection | None:
    domain = email.strip().lower().rsplit("@", 1)[-1]
    with system_session(db):
        rows = (
            db.execute(
                select(SsoConnection)
                .join(VerifiedDomain, VerifiedDomain.workspace_id == SsoConnection.workspace_id)
                .where(
                    VerifiedDomain.domain == domain,
                    VerifiedDomain.verified_at.is_not(None),
                    SsoConnection.is_active.is_(True),
                )
                .order_by(SsoConnection.id)
            )
            .scalars()
            .all()
        )
        for connection in rows:
            if _usable(db, connection):
                return connection
    return None


def get_connection_public(db: Session, connection_id: int) -> SsoConnection:
    """Load a connection for an unauthenticated sign-in, then scope the session to its workspace."""
    with system_session(db):
        connection = db.get(SsoConnection, connection_id)
        if connection is None or not _usable(db, connection):
            raise SsoError("This single sign-on connection isn't available")
    bind_session(db, connection.workspace_id)
    return connection


def password_login_blocked(db: Session, user: User) -> SsoConnection | None:
    """The enforcing connection that should be used instead of a password, if any.

    Owners of the enforcing workspace keep password access as a break-glass route.
    """
    connection = connection_for_email(db, user.email)
    if connection is None or not connection.enforce:
        return None
    owner = db.scalar(
        select(WorkspaceMember.id).where(
            WorkspaceMember.workspace_id == connection.workspace_id,
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.role == WorkspaceRole.OWNER,
        )
    )
    return None if owner else connection


# --- workspace administration -------------------------------------------------------------------


def add_domain(db: Session, workspace_id: int, domain: str) -> VerifiedDomain:
    normalized = domain.strip().lower().rstrip(".")
    from app.services.deliverability import valid_domain

    if not valid_domain(normalized):
        raise ValidationFailedError("Enter a valid domain, like example.com")
    if is_freemail_domain(normalized):
        raise ValidationFailedError("Public email domains like gmail.com can't be verified")
    taken = db.scalar(
        select(VerifiedDomain.id).where(
            VerifiedDomain.domain == normalized, VerifiedDomain.workspace_id == workspace_id
        )
    )
    if taken is not None:
        raise ConflictError("That domain is already added")
    with system_session(db):
        claimed = db.scalar(
            select(VerifiedDomain.id).where(
                VerifiedDomain.domain == normalized, VerifiedDomain.verified_at.is_not(None)
            )
        )
    if claimed is not None:
        raise ConflictError("That domain is already verified by another workspace")
    record = VerifiedDomain(
        workspace_id=workspace_id, domain=normalized, verification_token=secrets.token_hex(16)
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def verification_record(record: VerifiedDomain) -> str:
    return f"{VERIFICATION_PREFIX}{record.verification_token}"


def verify_domain(db: Session, workspace_id: int, domain_id: int, *, lookup=None) -> VerifiedDomain:
    from app.services.deliverability import LookupFailedError, dns_lookup

    record = db.scalar(
        select(VerifiedDomain).where(
            VerifiedDomain.id == domain_id, VerifiedDomain.workspace_id == workspace_id
        )
    )
    if record is None:
        raise NotFoundError("Domain not found")
    if record.verified_at is not None:
        return record
    try:
        values = (lookup or dns_lookup)(record.domain, "TXT")
    except LookupFailedError as exc:
        raise ValidationFailedError("DNS lookup timed out. Try again in a minute.") from exc
    if verification_record(record) not in [v.strip() for v in values]:
        raise ValidationFailedError(
            f'We couldn\'t find the TXT record "{verification_record(record)}" on '
            f"{record.domain} yet. DNS changes can take a few minutes to appear."
        )
    with system_session(db):
        claimed = db.scalar(
            select(VerifiedDomain.id).where(
                VerifiedDomain.domain == record.domain,
                VerifiedDomain.verified_at.is_not(None),
                VerifiedDomain.id != record.id,
            )
        )
    if claimed is not None:
        raise ConflictError("That domain is already verified by another workspace")
    record.verified_at = _now()
    db.commit()
    db.refresh(record)
    return record


def save_connection(
    db: Session, workspace: Workspace, data: dict, connection: SsoConnection | None = None
) -> SsoConnection:
    protocol = data.get("protocol") or (connection.protocol if connection else None)
    if protocol not in ("oidc", "saml"):
        raise ValidationFailedError("Choose OIDC or SAML")
    features = features_for(workspace)
    if protocol == "saml" and not features.saml:
        raise ValidationFailedError("SAML is available on the Enterprise plan")
    if not features.sso:
        raise ValidationFailedError("Single sign-on isn't included in your plan")
    connection = connection or SsoConnection(workspace_id=workspace.id, protocol=protocol)
    for field in (
        "display_name",
        "enforce",
        "default_role",
        "oidc_issuer",
        "oidc_client_id",
        "saml_idp_entity_id",
        "saml_idp_sso_url",
        "saml_idp_certificate",
        "is_active",
    ):
        if field in data and data[field] is not None:
            setattr(connection, field, data[field])
    if data.get("oidc_client_secret"):
        connection.oidc_client_secret_encrypted = encrypt_secret_payload(data["oidc_client_secret"])
    if connection.is_active:
        missing = (
            [f for f in ("oidc_issuer", "oidc_client_id") if not getattr(connection, f)]
            if protocol == "oidc"
            else [
                f
                for f in ("saml_idp_entity_id", "saml_idp_sso_url", "saml_idp_certificate")
                if not getattr(connection, f)
            ]
        )
        if missing:
            raise ValidationFailedError(
                "Fill in " + ", ".join(m.replace("_", " ") for m in missing)
            )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection
