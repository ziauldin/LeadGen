from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin, TimestampUpdatedMixin
from app.models.workspace import TenantScoped


class SsoConnection(Base, TenantScoped, TimestampUpdatedMixin):
    """A workspace's own identity provider (OIDC or SAML 2.0)."""

    __tablename__ = "sso_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    protocol: Mapped[str] = mapped_column(String(10), nullable=False)  # oidc | saml
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Members with an email at a verified domain must sign in through this provider.
    enforce: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_role: Mapped[str] = mapped_column(String(20), default="member", nullable=False)
    oidc_issuer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    oidc_client_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oidc_client_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    saml_idp_entity_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    saml_idp_sso_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    saml_idp_certificate: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VerifiedDomain(Base, TenantScoped, TimestampMixin):
    """An email domain a workspace has proved it owns (DNS TXT record)."""

    __tablename__ = "verified_domains"
    __table_args__ = (UniqueConstraint("workspace_id", "domain", name="uq_verified_domains_ws"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    verification_token: Mapped[str] = mapped_column(String(64), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExternalIdentity(Base, TimestampMixin):
    """A sign-in identity from Google, Microsoft or a workspace IdP, linked to a user."""

    __tablename__ = "external_identities"
    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_external_identities_provider_subject"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # google | microsoft | sso:<id>
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SsoLoginState(Base):
    """Single-use state for an in-flight sign-in (OIDC state/nonce/PKCE, SAML request id)."""

    __tablename__ = "sso_login_states"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    connection_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    code_verifier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    next_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    link_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
