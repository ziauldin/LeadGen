from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import UserRole
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.niche import Niche
    from app.models.provider_credential import ProviderCredential
    from app.models.user_settings import UserSettings


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        String(50),
        default=UserRole.OPERATOR,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Platform operator with access to the admin back office (granted from the CLI only).
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # Bumped on password reset / "log out everywhere"; access tokens carry it as `ver`.
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Two-factor authentication (TOTP). The secret is encrypted; recovery codes are hashed.
    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recovery_code_hashes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    totp_last_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "workspaces.id", ondelete="SET NULL", use_alter=True, name="fk_users_last_workspace"
        ),
        nullable=True,
    )

    @property
    def mfa_enabled(self) -> bool:
        return self.totp_enabled_at is not None and bool(self.totp_secret_encrypted)

    niches: Mapped[list[Niche]] = relationship(back_populates="user", passive_deletes=True)
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="actor")
    settings: Mapped[UserSettings | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    provider_credentials: Mapped[list[ProviderCredential]] = relationship(
        back_populates="user",
        passive_deletes=True,
    )
