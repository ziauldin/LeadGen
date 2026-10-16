"""admin back office: platform superusers, suspension reasons, per-workspace feature flags

Revision ID: 2e3f4a5b6c7d
Revises: 1d2e3f4a5b6c
Create Date: 2026-10-19 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2e3f4a5b6c7d"
down_revision: str | None = "1d2e3f4a5b6c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table("workspaces") as batch:
        batch.add_column(sa.Column("sending_suspended_reason", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("feature_flags", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("workspaces") as batch:
        batch.drop_column("feature_flags")
        batch.drop_column("sending_suspended_reason")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("is_superuser")
