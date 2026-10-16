from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin
from app.models.workspace import TenantScoped


class DataRequest(Base, TenantScoped, TimestampMixin):
    """A data subject request (export or erase one person) or a whole-workspace export."""

    __tablename__ = "data_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # export | erase | workspace_export
    # Kept for exports so the file can be named; replaced by the hash once an erasure finishes.
    subject_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    requested_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
