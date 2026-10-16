from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class WorkspaceRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


ROLE_RANK = {WorkspaceRole.MEMBER: 1, WorkspaceRole.ADMIN: 2, WorkspaceRole.OWNER: 3}

DEFAULT_SENDING_DAYS = [0, 1, 2, 3, 4]  # Monday-Friday (Python weekday numbers)


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    plan: Mapped[str] = mapped_column(String(30), default="free", nullable=False)
    plan_overrides: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey(
            "users.id", ondelete="SET NULL", use_alter=True, name="fk_workspaces_created_by"
        ),
        nullable=True,
    )
    # Set when the workspace is flagged for abuse (e.g. complaint spikes); blocks sending.
    sending_suspended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Members must have two-factor authentication on to use this workspace.
    require_2fa: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (UniqueConstraint("slug", name="uq_workspaces_slug"),)

    members: Mapped[list[WorkspaceMember]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    settings: Mapped[WorkspaceSettings | None] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
        uselist=False,
    )


class WorkspaceMember(Base, TimestampMixin):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_workspace_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default=WorkspaceRole.MEMBER, nullable=False)
    # Members can be given a custom role (Enterprise) instead of the built-in member set.
    custom_role_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "workspace_roles.id", ondelete="SET NULL", name="fk_workspace_members_custom_role_id"
        ),
        index=True,
        nullable=True,
    )

    workspace: Mapped[Workspace] = relationship(back_populates="members")
    user: Mapped[User] = relationship()
    custom_role: Mapped[CustomRole | None] = relationship()


class CustomRole(Base, TimestampMixin):
    """A named set of permissions an Enterprise workspace defines for its members."""

    __tablename__ = "workspace_roles"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_workspace_roles_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    permissions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class WorkspaceInvitation(Base, TimestampMixin):
    __tablename__ = "workspace_invitations"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_workspace_invitations_token_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), default=WorkspaceRole.MEMBER, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    invited_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped[Workspace] = relationship()


class WorkspaceSettings(Base):
    __tablename__ = "workspace_settings"
    __table_args__ = (UniqueConstraint("workspace_id", name="uq_workspace_settings_workspace"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    company_website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reply_to_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone_guidelines: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_mode: Mapped[str] = mapped_column(String(20), default="off", nullable=False)
    default_sending_window_start: Mapped[str] = mapped_column(
        String(5),
        default="09:00",
        nullable=False,
    )
    default_sending_window_end: Mapped[str] = mapped_column(
        String(5),
        default="17:00",
        nullable=False,
    )
    sending_days: Mapped[list] = mapped_column(
        JSON,
        default=lambda: list(DEFAULT_SENDING_DAYS),
        nullable=False,
    )
    # Data governance
    require_lia_note: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retention_uncontacted_lead_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retention_reply_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="settings")


class UsageCounter(Base):
    __tablename__ = "usage_counters"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "metric",
            "period_key",
            name="uq_usage_counters_workspace_metric_period",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    metric: Mapped[str] = mapped_column(String(50), nullable=False)
    period_key: Mapped[str] = mapped_column(String(10), nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class TenantScoped:
    """Mixin for rows owned by a workspace. Queries are filtered automatically (see tenancy)."""

    @declared_attr
    def workspace_id(cls) -> Mapped[int]:
        return mapped_column(
            ForeignKey("workspaces.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )
