from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.lead import Lead
    from app.models.search_query import SearchQuery
    from app.models.user import User


class Niche(Base, TimestampMixin):
    __tablename__ = "niches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    industry: Mapped[str] = mapped_column(String(255), nullable=False)
    target_roles: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    keywords: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    exclusion_keywords: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    company_size_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    company_size_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped[User] = relationship(back_populates="niches")
    search_queries: Mapped[list[SearchQuery]] = relationship(
        back_populates="niche",
        cascade="all, delete-orphan",
    )
    leads: Mapped[list[Lead]] = relationship(back_populates="niche", cascade="all, delete-orphan")
    campaigns: Mapped[list[Campaign]] = relationship(
        back_populates="niche",
        cascade="all, delete-orphan",
    )
