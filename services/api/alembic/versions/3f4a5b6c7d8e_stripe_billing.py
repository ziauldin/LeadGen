"""stripe billing: subscriptions, billing webhook events, workspace trials

Revision ID: 3f4a5b6c7d8e
Revises: 2e3f4a5b6c7d
Create Date: 2026-10-20 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3f4a5b6c7d8e"
down_revision: str | None = "2e3f4a5b6c7d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BYPASS = "current_setting('app.bypass_rls', true) = 'on'"
OWN = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::integer"


def upgrade() -> None:
    with op.batch_alter_table("workspaces") as batch:
        batch.add_column(sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stripe_customer_id", sa.String(length=64), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=64), nullable=True),
        sa.Column("plan", sa.String(length=30), nullable=True),
        sa.Column("interval", sa.String(length=10), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("past_due_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seats", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", name="uq_subscriptions_workspace"),
    )
    op.create_index("ix_subscriptions_workspace_id", "subscriptions", ["workspace_id"])
    op.create_index("ix_subscriptions_stripe_customer_id", "subscriptions", ["stripe_customer_id"])
    op.create_index(
        "ix_subscriptions_stripe_subscription_id", "subscriptions", ["stripe_subscription_id"]
    )

    op.create_table(
        "billing_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stripe_event_id", sa.String(length=64), nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.UniqueConstraint("stripe_event_id", name="uq_billing_events_stripe_event"),
    )
    op.create_index("ix_billing_events_workspace_id", "billing_events", ["workspace_id"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE subscriptions FORCE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY tenant_isolation ON subscriptions "
            f"USING ({BYPASS} OR {OWN}) WITH CHECK ({BYPASS} OR {OWN})",
        )


def downgrade() -> None:
    op.drop_index("ix_billing_events_workspace_id", table_name="billing_events")
    op.drop_table("billing_events")
    op.drop_index("ix_subscriptions_stripe_subscription_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_stripe_customer_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_workspace_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    with op.batch_alter_table("workspaces") as batch:
        batch.drop_column("trial_ends_at")
