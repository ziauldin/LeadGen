"""workspaces (expand): new tenant tables and nullable workspace_id columns

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-10-16 10:00:00.000000

Deploy note: this is part 1 of 3 (expand -> backfill -> contract). Scale the worker and beat
services to zero before deploying, then deploy the API (which runs the migrations), then bring
the worker and beat back.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "niches",
    "search_queries",
    "leads",
    "companies",
    "email_contacts",
    "campaigns",
    "campaign_steps",
    "email_messages",
    "replies",
    "provider_credentials",
    "suppressions",
    "audit_logs",
)


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("plan", sa.String(length=30), nullable=False, server_default="free"),
        sa.Column("plan_overrides", sa.JSON(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("sending_suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.UniqueConstraint("slug", name="uq_workspaces_slug"),
    )

    op.create_table(
        "workspace_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="member"),
        _created_at(),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_workspace_user"),
    )
    op.create_index("ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"])
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])

    op.create_table(
        "workspace_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="member"),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "invited_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.UniqueConstraint("token_hash", name="uq_workspace_invitations_token_hash"),
    )
    op.create_index(
        "ix_workspace_invitations_workspace_id",
        "workspace_invitations",
        ["workspace_id"],
    )
    op.create_index("ix_workspace_invitations_email", "workspace_invitations", ["email"])

    op.create_table(
        "workspace_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sender_name", sa.String(length=255), nullable=True),
        sa.Column("sender_company", sa.String(length=255), nullable=True),
        sa.Column("business_address", sa.String(length=500), nullable=True),
        sa.Column("company_website", sa.String(length=500), nullable=True),
        sa.Column("reply_to_domain", sa.String(length=255), nullable=True),
        sa.Column("product_description", sa.Text(), nullable=True),
        sa.Column("tone_guidelines", sa.Text(), nullable=True),
        sa.Column("ai_mode", sa.String(length=20), nullable=False, server_default="off"),
        sa.Column(
            "default_sending_window_start",
            sa.String(length=5),
            nullable=False,
            server_default="09:00",
        ),
        sa.Column(
            "default_sending_window_end",
            sa.String(length=5),
            nullable=False,
            server_default="17:00",
        ),
        sa.Column("sending_days", sa.JSON(), nullable=False, server_default="[0, 1, 2, 3, 4]"),
        sa.UniqueConstraint("workspace_id", name="uq_workspace_settings_workspace"),
    )
    op.create_index("ix_workspace_settings_workspace_id", "workspace_settings", ["workspace_id"])

    op.create_table(
        "usage_counters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric", sa.String(length=50), nullable=False),
        sa.Column("period_key", sa.String(length=10), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "workspace_id",
            "metric",
            "period_key",
            name="uq_usage_counters_workspace_metric_period",
        ),
    )
    op.create_index("ix_usage_counters_workspace_id", "usage_counters", ["workspace_id"])

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("last_workspace_id", sa.Integer(), nullable=True))

    for table in TENANT_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("workspace_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("email_contacts") as batch:
        batch.add_column(sa.Column("source_provider", sa.String(length=50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("email_contacts") as batch:
        batch.drop_column("source_provider")
    for table in reversed(TENANT_TABLES):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("workspace_id")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("last_workspace_id")
    op.drop_table("usage_counters")
    op.drop_table("workspace_settings")
    op.drop_table("workspace_invitations")
    op.drop_table("workspace_members")
    op.drop_table("workspaces")
