"""data governance: lawful basis on leads, hashed suppressions, data requests, retention settings

Revision ID: 0c1d2e3f4a5b
Revises: f8a9b0c1d2e3
Create Date: 2026-10-18 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0c1d2e3f4a5b"
down_revision: str | None = "f8a9b0c1d2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BYPASS = "current_setting('app.bypass_rls', true) = 'on'"
OWN = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::integer"


def upgrade() -> None:
    with op.batch_alter_table("leads") as batch:
        batch.add_column(
            sa.Column(
                "lawful_basis",
                sa.String(length=30),
                nullable=False,
                server_default="legitimate_interest",
            )
        )
        batch.add_column(sa.Column("lawful_basis_note", sa.Text(), nullable=True))

    with op.batch_alter_table("suppressions") as batch:
        batch.add_column(sa.Column("email_hash", sa.String(length=64), nullable=True))
        batch.create_index("ix_suppressions_email_hash", ["email_hash"])

    with op.batch_alter_table("workspace_settings") as batch:
        batch.add_column(
            sa.Column("require_lia_note", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(sa.Column("retention_uncontacted_lead_days", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("retention_reply_days", sa.Integer(), nullable=True))

    op.create_table(
        "data_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("subject_email", sa.String(length=255), nullable=True),
        sa.Column("subject_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column(
            "requested_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("file_key", sa.String(length=500), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_data_requests_workspace_id", "data_requests", ["workspace_id"])
    op.create_index("ix_data_requests_subject_hash", "data_requests", ["subject_hash"])
    op.create_index("ix_data_requests_status", "data_requests", ["status"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE data_requests ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE data_requests FORCE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY tenant_isolation ON data_requests "
            f"USING ({BYPASS} OR {OWN}) WITH CHECK ({BYPASS} OR {OWN})",
        )


def downgrade() -> None:
    op.drop_index("ix_data_requests_status", table_name="data_requests")
    op.drop_index("ix_data_requests_subject_hash", table_name="data_requests")
    op.drop_index("ix_data_requests_workspace_id", table_name="data_requests")
    op.drop_table("data_requests")
    with op.batch_alter_table("workspace_settings") as batch:
        batch.drop_column("retention_reply_days")
        batch.drop_column("retention_uncontacted_lead_days")
        batch.drop_column("require_lia_note")
    with op.batch_alter_table("suppressions") as batch:
        batch.drop_index("ix_suppressions_email_hash")
        batch.drop_column("email_hash")
    with op.batch_alter_table("leads") as batch:
        batch.drop_column("lawful_basis_note")
        batch.drop_column("lawful_basis")
