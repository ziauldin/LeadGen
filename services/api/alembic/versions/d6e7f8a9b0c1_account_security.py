"""account security: two-factor authentication, password change time, workspace 2FA policy

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-10-17 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: str | None = "c5d6e7f8a9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("totp_secret_encrypted", sa.Text(), nullable=True))
        batch.add_column(sa.Column("totp_enabled_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("recovery_code_hashes", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("totp_last_step", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("workspaces") as batch:
        batch.add_column(
            sa.Column("require_2fa", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    with op.batch_alter_table("workspaces") as batch:
        batch.drop_column("require_2fa")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("password_changed_at")
        batch.drop_column("totp_last_step")
        batch.drop_column("recovery_code_hashes")
        batch.drop_column("totp_enabled_at")
        batch.drop_column("totp_secret_encrypted")
