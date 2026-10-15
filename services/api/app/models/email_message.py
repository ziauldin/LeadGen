from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import BounceStatus, EmailMessageStatus, ReplyStatus
from app.models.mixins import TimestampUpdatedMixin
from app.models.workspace import TenantScoped

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.lead import Lead
    from app.models.reply import Reply


class EmailMessage(Base, TenantScoped, TimestampUpdatedMixin):
    __tablename__ = "email_messages"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_email_messages_idempotency_key"),
        UniqueConstraint("reply_token", name="uq_email_messages_reply_token"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[EmailMessageStatus] = mapped_column(
        String(50),
        default=EmailMessageStatus.DRAFT,
        nullable=False,
        index=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    reply_status: Mapped[ReplyStatus] = mapped_column(
        String(50),
        default=ReplyStatus.NONE,
        nullable=False,
    )
    bounce_status: Mapped[BounceStatus] = mapped_column(
        String(50),
        default=BounceStatus.NONE,
        nullable=False,
    )
    unsubscribe_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)

    # Delivery pipeline
    recipient_domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sending_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    send_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rfc_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    reply_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sender_credential_id: Mapped[int | None] = mapped_column(
        ForeignKey("provider_credentials.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Review
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    edited_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # How the content was produced
    generation_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    campaign: Mapped[Campaign | None] = relationship(back_populates="email_messages")
    lead: Mapped[Lead] = relationship(back_populates="email_messages")
    replies: Mapped[list[Reply]] = relationship(
        back_populates="email_message",
        cascade="all, delete-orphan",
    )
