from __future__ import annotations

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin
from app.models.workspace import TenantScoped


class CampaignSender(Base, TenantScoped, TimestampMixin):
    """A sending account in a campaign's rotation pool."""

    __tablename__ = "campaign_senders"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id", "credential_id", name="uq_campaign_senders_campaign_credential"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    credential_id: Mapped[int] = mapped_column(
        ForeignKey("provider_credentials.id", ondelete="CASCADE"), index=True
    )
