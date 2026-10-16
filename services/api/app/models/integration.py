"""CRM integrations (HubSpot, Pipedrive): connections, links to remote records, and a sync log."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin, TimestampUpdatedMixin
from app.models.workspace import TenantScoped


class IntegrationConnection(Base, TenantScoped, TimestampUpdatedMixin):
    """One connected CRM account per provider per workspace. Tokens are stored encrypted."""

    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint("workspace_id", "provider", name="uq_integration_connections_provider"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)  # hubspot | pipedrive
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # active | error
    account_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    config_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    # {"push_contacts": bool, "push_deals": bool, "pull_status": bool}
    settings: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    connected_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class IntegrationLink(Base, TenantScoped, TimestampUpdatedMixin):
    """Which remote record a lead (contact) or deal was pushed to."""

    __tablename__ = "integration_links"
    __table_args__ = (
        UniqueConstraint(
            "connection_id", "object_type", "local_id", name="uq_integration_links_object"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"), index=True
    )
    object_type: Mapped[str] = mapped_column(String(20), nullable=False)  # contact | deal
    local_id: Mapped[int] = mapped_column(Integer, nullable=False)
    remote_id: Mapped[str] = mapped_column(String(64), nullable=False)
    remote_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # deals
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IntegrationSyncLog(Base, TenantScoped, TimestampMixin):
    __tablename__ = "integration_sync_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"), index=True
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # push | pull
    object_type: Mapped[str] = mapped_column(String(20), nullable=False)
    local_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remote_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)  # ok | error | skipped
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
