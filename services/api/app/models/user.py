from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import UserRole
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.niche import Niche
    from app.models.provider_credential import ProviderCredential
    from app.models.user_settings import UserSettings


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        String(50),
        default=UserRole.OPERATOR,
        nullable=False,
    )

    niches: Mapped[list[Niche]] = relationship(back_populates="user", cascade="all, delete-orphan")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="actor")
    settings: Mapped[UserSettings | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    provider_credentials: Mapped[list[ProviderCredential]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
