"""crm integrations: connections, links to remote records, sync log

Revision ID: a0b1c2d3e4f5
Revises: 9f0a1b2c3d4e
Create Date: 2026-10-23 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a0b1c2d3e4f5"
down_revision: str | None = "9f0a1b2c3d4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BYPASS = "current_setting('app.bypass_rls', true) = 'on'"
OWN = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::integer"
TABLES = ("integration_connections", "integration_links", "integration_sync_logs")


def _workspace() -> sa.Column:
    return sa.Column(
        "workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )


def _connection() -> sa.Column:
    return sa.Column(
        "connection_id",
        sa.Integer(),
        sa.ForeignKey("integration_connections.id", ondelete="CASCADE"),
        nullable=False,
    )


def _timestamps(updated: bool = True) -> list[sa.Column]:
    columns = [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    ]
    if updated:
        columns.append(
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
        )
    return columns


def upgrade() -> None:
    op.create_table(
        "integration_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        _workspace(),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("account_label", sa.String(length=255), nullable=True),
        sa.Column("config_encrypted", sa.Text(), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column(
            "connected_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("workspace_id", "provider", name="uq_integration_connections_provider"),
    )
    op.create_index(
        "ix_integration_connections_workspace_id", "integration_connections", ["workspace_id"]
    )

    op.create_table(
        "integration_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        _workspace(),
        _connection(),
        sa.Column("object_type", sa.String(length=20), nullable=False),
        sa.Column("local_id", sa.Integer(), nullable=False),
        sa.Column("remote_id", sa.String(length=64), nullable=False),
        sa.Column("remote_status", sa.String(length=20), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint(
            "connection_id", "object_type", "local_id", name="uq_integration_links_object"
        ),
    )
    for column in ("workspace_id", "connection_id"):
        op.create_index(f"ix_integration_links_{column}", "integration_links", [column])

    op.create_table(
        "integration_sync_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        _workspace(),
        _connection(),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("object_type", sa.String(length=20), nullable=False),
        sa.Column("local_id", sa.Integer(), nullable=True),
        sa.Column("remote_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=True),
        *_timestamps(updated=False),
    )
    for column in ("workspace_id", "connection_id"):
        op.create_index(f"ix_integration_sync_logs_{column}", "integration_sync_logs", [column])

    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY tenant_isolation ON {table} "
                f"USING ({BYPASS} OR {OWN}) WITH CHECK ({BYPASS} OR {OWN})",
            )


def downgrade() -> None:
    for column in ("workspace_id", "connection_id"):
        op.drop_index(f"ix_integration_sync_logs_{column}", table_name="integration_sync_logs")
    op.drop_table("integration_sync_logs")
    for column in ("workspace_id", "connection_id"):
        op.drop_index(f"ix_integration_links_{column}", table_name="integration_links")
    op.drop_table("integration_links")
    op.drop_index("ix_integration_connections_workspace_id", table_name="integration_connections")
    op.drop_table("integration_connections")
