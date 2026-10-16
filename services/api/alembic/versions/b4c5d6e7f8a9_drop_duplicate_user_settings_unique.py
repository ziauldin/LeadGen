"""drop the duplicate unique constraint on user_settings.user_id (PostgreSQL)

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-10-17 09:00:00.000000

The original migration created both a unique constraint and a unique index on the same
column. The unique index stays; the redundant constraint only existed on PostgreSQL.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b4c5d6e7f8a9"
down_revision: str | None = "a3b4c5d6e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE user_settings DROP CONSTRAINT IF EXISTS user_settings_user_id_key")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE user_settings ADD CONSTRAINT user_settings_user_id_key UNIQUE (user_id)",
        )
