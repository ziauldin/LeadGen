from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import CampaignStatus
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.email_message import EmailMessage
    from app.models.niche import Niche


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        String(50),
        default=CampaignStatus.DRAFT,
        nullable=False,
    )
    daily_send_limit: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    sending_window_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    sending_window_end: Mapped[str | None] = mapped_column(String(5), nullable=True)

    niche: Mapped[Niche] = relationship(back_populates="campaigns")
    steps: Mapped[list[CampaignStep]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="CampaignStep.step_number",
    )
    email_messages: Mapped[list[EmailMessage]] = relationship(back_populates="campaign")


class CampaignStep(Base):
    __tablename__ = "campaign_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        index=True,
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    delay_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    subject_template: Mapped[str] = mapped_column(String(500), nullable=False)
    body_template: Mapped[str] = mapped_column(String, nullable=False)

    campaign: Mapped[Campaign] = relationship(back_populates="steps")
