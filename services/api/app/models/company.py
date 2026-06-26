from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import EnrichmentStatus
from app.models.mixins import TimestampUpdatedMixin

if TYPE_CHECKING:
    from app.models.email_contact import EmailContact
    from app.models.lead import Lead


class Company(Base, TimestampUpdatedMixin):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contact_page_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    about_page_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    robots_checked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enrichment_status: Mapped[EnrichmentStatus] = mapped_column(
        String(50),
        default=EnrichmentStatus.PENDING,
        nullable=False,
    )
    enrichment_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    leads: Mapped[list[Lead]] = relationship(back_populates="company")
    email_contacts: Mapped[list[EmailContact]] = relationship(back_populates="company")
