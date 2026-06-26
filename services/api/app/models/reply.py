from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ReplyClassification

if TYPE_CHECKING:
    from app.models.email_message import EmailMessage


class Reply(Base):
    __tablename__ = "replies"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_message_id: Mapped[int] = mapped_column(
        ForeignKey("email_messages.id", ondelete="CASCADE"),
        index=True,
    )
    from_email: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[ReplyClassification] = mapped_column(
        String(50),
        default=ReplyClassification.UNKNOWN,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    email_message: Mapped[EmailMessage] = relationship(back_populates="replies")
