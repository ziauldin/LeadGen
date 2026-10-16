from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import EmailType
from app.models.mixins import TimestampMixin
from app.models.workspace import TenantScoped

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.lead import Lead


class EmailContact(Base, TenantScoped, TimestampMixin):
    __tablename__ = "email_contacts"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "lead_id", "email", name="uq_email_contacts_workspace_lead_email"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int | None] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email_type: Mapped[EmailType] = mapped_column(
        String(50), default=EmailType.GENERIC, nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_role_based: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_personal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Verification: valid | risky | invalid | unknown (None = not checked yet).
    verification_status: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    verification_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verification_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lead: Mapped[Lead | None] = relationship(back_populates="email_contacts")
    company: Mapped[Company | None] = relationship(back_populates="email_contacts")
