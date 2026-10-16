"""Stripe subscriptions and the billing webhook events they're kept in sync from."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin, TimestampUpdatedMixin
from app.models.workspace import TenantScoped


class Subscription(Base, TenantScoped, TimestampUpdatedMixin):
    """A workspace's Stripe customer and (current) subscription. One row per workspace."""

    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("workspace_id", name="uq_subscriptions_workspace"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    plan: Mapped[str | None] = mapped_column(String(30), nullable=True)
    interval: Mapped[str | None] = mapped_column(String(10), nullable=True)  # month | year
    # Stripe's status: trialing | active | past_due | canceled | unpaid | incomplete | ...
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    past_due_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    seats: Mapped[int | None] = mapped_column(Integer, nullable=True)


class BillingEvent(Base):
    """A verified Stripe webhook event, stored once so retries are harmless."""

    __tablename__ = "billing_events"
    __table_args__ = (UniqueConstraint("stripe_event_id", name="uq_billing_events_stripe_event"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stripe_event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    workspace_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class CreditTransaction(Base, TenantScoped, TimestampMixin):
    """One change to a workspace's credit balance: a purchase, a grant, or a day's usage."""

    __tablename__ = "credit_transactions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "reference", name="uq_credit_transactions_reference"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # + added, - used
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # purchase | grant | usage
    metric: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Stripe checkout session id for purchases, "usage:<metric>:<date>" for usage.
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
