from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import BounceStatus, EmailMessageStatus, ReplyStatus

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.lead import Lead
    from app.models.reply import Reply


class EmailMessage(Base):
    __tablename__ = "email_messages"

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
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
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

    campaign: Mapped[Campaign | None] = relationship(back_populates="email_messages")
    lead: Mapped[Lead] = relationship(back_populates="email_messages")
    replies: Mapped[list[Reply]] = relationship(
        back_populates="email_message",
        cascade="all, delete-orphan",
    )
