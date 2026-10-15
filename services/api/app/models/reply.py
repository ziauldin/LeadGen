from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ReplyClassification
from app.models.workspace import TenantScoped

if TYPE_CHECKING:
    from app.models.email_message import EmailMessage


class Reply(Base, TenantScoped):
    __tablename__ = "replies"

    id: Mapped[int] = mapped_column(primary_key=True)
    # NULL until linked: replies we could not match are kept for manual linking.
    email_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("email_messages.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    lead_id: Mapped[int | None] = mapped_column(
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    enrollment_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaign_enrollments.id", ondelete="SET NULL"),
        nullable=True,
    )
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    message_id_header: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    in_reply_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    classified_by: Mapped[str | None] = mapped_column(String(10), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_auto_reply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    from_email: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[ReplyClassification] = mapped_column(
        String(50),
        default=ReplyClassification.UNKNOWN,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    email_message: Mapped[EmailMessage | None] = relationship(back_populates="replies")
