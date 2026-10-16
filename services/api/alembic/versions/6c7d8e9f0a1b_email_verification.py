"""email verification: per-contact verification status, block-risky workspace setting

Revision ID: 6c7d8e9f0a1b
Revises: 5b6c7d8e9f0a
Create Date: 2026-10-21 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6c7d8e9f0a1b"
down_revision: str | None = "5b6c7d8e9f0a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("email_contacts") as batch:
        batch.add_column(sa.Column("verification_status", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("verification_detail", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("verification_provider", sa.String(length=30), nullable=True))
        batch.add_column(sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_email_contacts_verification_status", ["verification_status"])
    with op.batch_alter_table("workspace_settings") as batch:
        batch.add_column(
            sa.Column("block_risky_emails", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("workspace_settings") as batch:
        batch.drop_column("block_risky_emails")
    with op.batch_alter_table("email_contacts") as batch:
        batch.drop_index("ix_email_contacts_verification_status")
        batch.drop_column("verified_at")
        batch.drop_column("verification_provider")
        batch.drop_column("verification_detail")
        batch.drop_column("verification_status")
