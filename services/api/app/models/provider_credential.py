from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ProviderCredentialStatus, ProviderName, ProviderType
from app.models.mixins import TimestampUpdatedMixin
from app.models.workspace import TenantScoped

if TYPE_CHECKING:
    from app.models.user import User


class ProviderCredential(Base, TenantScoped, TimestampUpdatedMixin):
    __tablename__ = "provider_credentials"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "provider_type",
            "provider_name",
            name="uq_workspace_provider",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Creator. Kept when the creator leaves; the row belongs to the workspace.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    provider_type: Mapped[ProviderType] = mapped_column(String(20), nullable=False)
    provider_name: Mapped[ProviderName] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_config_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    masked_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[ProviderCredentialStatus] = mapped_column(
        String(30),
        default=ProviderCredentialStatus.NOT_CONFIGURED,
        nullable=False,
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User | None] = relationship(back_populates="provider_credentials")
