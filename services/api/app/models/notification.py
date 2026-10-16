"""In-app notifications, per-user preferences and lifecycle email bookkeeping."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin, TimestampUpdatedMixin
from app.models.workspace import TenantScoped


class Notification(Base, TenantScoped, TimestampMixin):
    """Something a person should know about, shown under the bell in the app."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class NotificationPreference(Base, TimestampUpdatedMixin):
    """Which notifications a person wants, per channel: {"positive_reply": {"email": true}}."""

    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", name="uq_notification_preferences_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class LifecycleEmail(Base, TimestampMixin):
    """A lifecycle email that was sent, so each one goes out at most once per key."""

    __tablename__ = "lifecycle_emails"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_lifecycle_emails_user_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # e.g. "welcome", "verify_reminder", "trial_ending:2026-10-30", "digest:2026-W42"
    key: Mapped[str] = mapped_column(String(100), nullable=False)
