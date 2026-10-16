"""connected mailboxes: per-account daily limits and pause state, campaign sender pools

Revision ID: 5b6c7d8e9f0a
Revises: 4a5b6c7d8e9f
Create Date: 2026-10-21 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5b6c7d8e9f0a"
down_revision: str | None = "4a5b6c7d8e9f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BYPASS = "current_setting('app.bypass_rls', true) = 'on'"
OWN = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::integer"


def upgrade() -> None:
    with op.batch_alter_table("provider_credentials") as batch:
        batch.add_column(sa.Column("daily_limit", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("disabled_reason", sa.String(length=255), nullable=True))

    op.create_table(
        "campaign_senders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            sa.Integer(),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "credential_id",
            sa.Integer(),
            sa.ForeignKey("provider_credentials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "campaign_id", "credential_id", name="uq_campaign_senders_campaign_credential"
        ),
    )
    op.create_index("ix_campaign_senders_workspace_id", "campaign_senders", ["workspace_id"])
    op.create_index("ix_campaign_senders_campaign_id", "campaign_senders", ["campaign_id"])
    op.create_index("ix_campaign_senders_credential_id", "campaign_senders", ["credential_id"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE campaign_senders ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE campaign_senders FORCE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY tenant_isolation ON campaign_senders "
            f"USING ({BYPASS} OR {OWN}) WITH CHECK ({BYPASS} OR {OWN})",
        )


def downgrade() -> None:
    op.drop_index("ix_campaign_senders_credential_id", table_name="campaign_senders")
    op.drop_index("ix_campaign_senders_campaign_id", table_name="campaign_senders")
    op.drop_index("ix_campaign_senders_workspace_id", table_name="campaign_senders")
    op.drop_table("campaign_senders")
    with op.batch_alter_table("provider_credentials") as batch:
        batch.drop_column("disabled_reason")
        batch.drop_column("disabled_at")
        batch.drop_column("daily_limit")
