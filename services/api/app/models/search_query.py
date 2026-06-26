from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import SearchProvider, SearchStatus
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.niche import Niche


class SearchQuery(Base, TimestampMixin):
    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(primary_key=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id", ondelete="CASCADE"), index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[SearchProvider] = mapped_column(String(50), nullable=False)
    status: Mapped[SearchStatus] = mapped_column(
        String(50),
        default=SearchStatus.PENDING,
        nullable=False,
    )
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    results: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    niche: Mapped[Niche] = relationship(back_populates="search_queries")
