from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import LeadStatus
from app.models.mixins import TimestampUpdatedMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.email_contact import EmailContact
    from app.models.email_message import EmailMessage
    from app.models.niche import Niche


class Lead(Base, TimestampUpdatedMixin):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    status: Mapped[LeadStatus] = mapped_column(
        String(50),
        default=LeadStatus.NEW,
        nullable=False,
        index=True,
    )
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    qualification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    compliance_source_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    niche: Mapped[Niche] = relationship(back_populates="leads")
    company: Mapped[Company | None] = relationship(back_populates="leads")
    email_contacts: Mapped[list[EmailContact]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
    )
    email_messages: Mapped[list[EmailMessage]] = relationship(back_populates="lead")
