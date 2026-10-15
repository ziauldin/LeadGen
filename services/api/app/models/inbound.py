from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.workspace import TenantScoped


class WebhookEvent(Base, TenantScoped):
    """A raw, signature-verified provider webhook. Stored first, processed asynchronously."""

    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_webhook_events_provider_event"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    credential_id: Mapped[int | None] = mapped_column(
        ForeignKey("provider_credentials.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # events | inbound
    event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmailEvent(Base, TenantScoped):
    """Delivery timeline for a message (delivered, bounces, complaints). No open tracking."""

    __tablename__ = "email_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("email_messages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    recipient_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class InboxCursor(Base, TenantScoped):
    """IMAP polling position for one inbox credential."""

    __tablename__ = "inbox_cursors"
    __table_args__ = (UniqueConstraint("credential_id", name="uq_inbox_cursors_credential"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    credential_id: Mapped[int] = mapped_column(
        ForeignKey("provider_credentials.id", ondelete="CASCADE"),
        nullable=False,
    )
    uidvalidity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_uid: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
