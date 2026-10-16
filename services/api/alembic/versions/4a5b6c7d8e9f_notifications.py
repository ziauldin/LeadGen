"""notifications: in-app notifications, preferences, lifecycle emails, Slack webhook

Revision ID: 4a5b6c7d8e9f
Revises: 3f4a5b6c7d8e
Create Date: 2026-10-20 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4a5b6c7d8e9f"
down_revision: str | None = "3f4a5b6c7d8e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BYPASS = "current_setting('app.bypass_rls', true) = 'on'"
OWN = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::integer"


def _created() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("link", sa.String(length=500), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        _created(),
    )
    op.create_index("ix_notifications_workspace_id", "notifications", ["workspace_id"])
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_read_at", "notifications", ["read_at"])

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("settings", sa.JSON(), nullable=False),
        _created(),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", name="uq_notification_preferences_user"),
    )
    op.create_index(
        "ix_notification_preferences_user_id", "notification_preferences", ["user_id"]
    )

    op.create_table(
        "lifecycle_emails",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("workspace_id", sa.Integer(), nullable=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        _created(),
        sa.UniqueConstraint("user_id", "key", name="uq_lifecycle_emails_user_key"),
    )
    op.create_index("ix_lifecycle_emails_user_id", "lifecycle_emails", ["user_id"])

    with op.batch_alter_table("workspace_settings") as batch:
        batch.add_column(sa.Column("slack_webhook_encrypted", sa.Text(), nullable=True))
        batch.add_column(sa.Column("slack_events", sa.JSON(), nullable=True))

    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE notifications FORCE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY tenant_isolation ON notifications "
            f"USING ({BYPASS} OR {OWN}) WITH CHECK ({BYPASS} OR {OWN})",
        )


def downgrade() -> None:
    with op.batch_alter_table("workspace_settings") as batch:
        batch.drop_column("slack_events")
        batch.drop_column("slack_webhook_encrypted")
    op.drop_index("ix_lifecycle_emails_user_id", table_name="lifecycle_emails")
    op.drop_table("lifecycle_emails")
    op.drop_index("ix_notification_preferences_user_id", table_name="notification_preferences")
    op.drop_table("notification_preferences")
    op.drop_index("ix_notifications_read_at", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("ix_notifications_workspace_id", table_name="notifications")
    op.drop_table("notifications")
