"""a/b tests: step variants and the variant each email used

Revision ID: 9f0a1b2c3d4e
Revises: 8e9f0a1b2c3d
Create Date: 2026-10-23 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f0a1b2c3d4e"
down_revision: str | None = "8e9f0a1b2c3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("campaign_steps") as batch:
        batch.add_column(sa.Column("variants", sa.JSON(), nullable=True))
    with op.batch_alter_table("email_messages") as batch:
        batch.add_column(sa.Column("variant", sa.String(length=5), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("email_messages") as batch:
        batch.drop_column("variant")
    with op.batch_alter_table("campaign_steps") as batch:
        batch.drop_column("variants")
