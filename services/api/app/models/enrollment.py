from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampUpdatedMixin
from app.models.workspace import TenantScoped

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.lead import Lead


class EnrollmentStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    REPLIED = "replied"
    BOUNCED = "bounced"
    OPTED_OUT = "opted_out"
    STOPPED = "stopped"
    FAILED = "failed"


TERMINAL = {
    EnrollmentStatus.COMPLETED,
    EnrollmentStatus.REPLIED,
    EnrollmentStatus.BOUNCED,
    EnrollmentStatus.OPTED_OUT,
    EnrollmentStatus.STOPPED,
    EnrollmentStatus.FAILED,
}


class CampaignEnrollment(Base, TenantScoped, TimestampUpdatedMixin):
    """One lead's progress through a campaign's sequence of steps."""

    __tablename__ = "campaign_enrollments"
    __table_args__ = (
        UniqueConstraint("campaign_id", "lead_id", name="uq_campaign_enrollments_campaign_lead"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        index=True,
    )
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default=EnrollmentStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_step_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_send_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    campaign: Mapped[Campaign] = relationship()
    lead: Mapped[Lead] = relationship()
