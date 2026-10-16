"""custom roles: workspace-defined permission sets for members

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-10-18 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: str | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "name", name="uq_workspace_roles_name"),
    )
    op.create_index("ix_workspace_roles_workspace_id", "workspace_roles", ["workspace_id"])
    with op.batch_alter_table("workspace_members") as batch:
        batch.add_column(sa.Column("custom_role_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_workspace_members_custom_role_id",
            "workspace_roles",
            ["custom_role_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_workspace_members_custom_role_id", ["custom_role_id"])
    op.create_index("ix_audit_logs_workspace_created", "audit_logs", ["workspace_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_workspace_created", table_name="audit_logs")
    with op.batch_alter_table("workspace_members") as batch:
        batch.drop_index("ix_workspace_members_custom_role_id")
        batch.drop_constraint("fk_workspace_members_custom_role_id", type_="foreignkey")
        batch.drop_column("custom_role_id")
    op.drop_index("ix_workspace_roles_workspace_id", table_name="workspace_roles")
    op.drop_table("workspace_roles")
