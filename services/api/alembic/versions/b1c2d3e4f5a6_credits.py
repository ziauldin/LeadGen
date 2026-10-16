"""credits: workspace credit balance and the credit ledger

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-10-24 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "a0b1c2d3e4f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BYPASS = "current_setting('app.bypass_rls', true) = 'on'"
OWN = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::integer"


def upgrade() -> None:
    with op.batch_alter_table("workspaces") as batch:
        batch.add_column(
            sa.Column("credit_balance", sa.Integer(), nullable=False, server_default="0")
        )

    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("metric", sa.String(length=50), nullable=True),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column(
            "actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("balance_after", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("workspace_id", "reference", name="uq_credit_transactions_reference"),
    )
    op.create_index(
        "ix_credit_transactions_workspace_id", "credit_transactions", ["workspace_id"]
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE credit_transactions ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE credit_transactions FORCE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY tenant_isolation ON credit_transactions "
            f"USING ({BYPASS} OR {OWN}) WITH CHECK ({BYPASS} OR {OWN})",
        )


def downgrade() -> None:
    op.drop_index("ix_credit_transactions_workspace_id", table_name="credit_transactions")
    op.drop_table("credit_transactions")
    with op.batch_alter_table("workspaces") as batch:
        batch.drop_column("credit_balance")
