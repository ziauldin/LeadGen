"""crm-lite: deal stages, deals, tasks, notes; auto-deal and meeting link settings

Revision ID: 8e9f0a1b2c3d
Revises: 7d8e9f0a1b2c
Create Date: 2026-10-22 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8e9f0a1b2c3d"
down_revision: str | None = "7d8e9f0a1b2c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BYPASS = "current_setting('app.bypass_rls', true) = 'on'"
OWN = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::integer"
TABLES = ("deal_stages", "deals", "tasks", "notes")


def _workspace() -> sa.Column:
    return sa.Column(
        "workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )


def _created() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _updated() -> sa.Column:
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "deal_stages",
        sa.Column("id", sa.Integer(), primary_key=True),
        _workspace(),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kind", sa.String(length=10), nullable=False, server_default="open"),
        sa.Column("probability", sa.Integer(), nullable=False, server_default="10"),
        _created(),
    )
    op.create_index("ix_deal_stages_workspace_id", "deal_stages", ["workspace_id"])

    op.create_table(
        "deals",
        sa.Column("id", sa.Integer(), primary_key=True),
        _workspace(),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "stage_id", sa.Integer(), sa.ForeignKey("deal_stages.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("value_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("expected_close_date", sa.Date(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        _created(),
        _updated(),
    )
    for column in ("workspace_id", "lead_id", "company_id", "stage_id", "owner_id"):
        op.create_index(f"ix_deals_{column}", "deals", [column])

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        _workspace(),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=True),
        sa.Column("deal_id", sa.Integer(), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=True),
        sa.Column("reminded_at", sa.DateTime(timezone=True), nullable=True),
        _created(),
        _updated(),
    )
    for column in ("workspace_id", "due_at", "done_at", "assignee_id", "lead_id", "deal_id"):
        op.create_index(f"ix_tasks_{column}", "tasks", [column])

    op.create_table(
        "notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        _workspace(),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=True),
        sa.Column("deal_id", sa.Integer(), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=True),
        _created(),
    )
    for column in ("workspace_id", "lead_id", "deal_id"):
        op.create_index(f"ix_notes_{column}", "notes", [column])

    with op.batch_alter_table("workspace_settings") as batch:
        batch.add_column(
            sa.Column("auto_create_deals", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch.add_column(sa.Column("meeting_link", sa.String(length=500), nullable=True))

    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY tenant_isolation ON {table} "
                f"USING ({BYPASS} OR {OWN}) WITH CHECK ({BYPASS} OR {OWN})",
            )


def downgrade() -> None:
    with op.batch_alter_table("workspace_settings") as batch:
        batch.drop_column("meeting_link")
        batch.drop_column("auto_create_deals")
    for column in ("workspace_id", "lead_id", "deal_id"):
        op.drop_index(f"ix_notes_{column}", table_name="notes")
    op.drop_table("notes")
    for column in ("workspace_id", "due_at", "done_at", "assignee_id", "lead_id", "deal_id"):
        op.drop_index(f"ix_tasks_{column}", table_name="tasks")
    op.drop_table("tasks")
    for column in ("workspace_id", "lead_id", "company_id", "stage_id", "owner_id"):
        op.drop_index(f"ix_deals_{column}", table_name="deals")
    op.drop_table("deals")
    op.drop_index("ix_deal_stages_workspace_id", table_name="deal_stages")
    op.drop_table("deal_stages")
