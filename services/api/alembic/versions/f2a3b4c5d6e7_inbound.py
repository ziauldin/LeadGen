"""inbound: webhook events, delivery events, inbox cursors, richer replies, suppression codes

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-10-16 15:00:00.000000

Existing replies get their lead and enrollment from the message they belong to.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _workspace_fk() -> sa.Column:
    return sa.Column(
        "workspace_id",
        sa.Integer(),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        _workspace_fk(),
        sa.Column(
            "credential_id",
            sa.Integer(),
            sa.ForeignKey("provider_credentials.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("provider", "event_id", name="uq_webhook_events_provider_event"),
    )
    op.create_index("ix_webhook_events_workspace_id", "webhook_events", ["workspace_id"])
    op.create_index("ix_webhook_events_status", "webhook_events", ["status"])

    op.create_table(
        "email_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        _workspace_fk(),
        sa.Column(
            "email_message_id",
            sa.Integer(),
            sa.ForeignKey("email_messages.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("recipient_email", sa.String(length=255), nullable=True),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
    )
    for column in ("workspace_id", "email_message_id", "recipient_email"):
        op.create_index(f"ix_email_events_{column}", "email_events", [column])

    op.create_table(
        "inbox_cursors",
        sa.Column("id", sa.Integer(), primary_key=True),
        _workspace_fk(),
        sa.Column(
            "credential_id",
            sa.Integer(),
            sa.ForeignKey("provider_credentials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("uidvalidity", sa.Integer(), nullable=True),
        sa.Column("last_uid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.UniqueConstraint("credential_id", name="uq_inbox_cursors_credential"),
    )
    op.create_index("ix_inbox_cursors_workspace_id", "inbox_cursors", ["workspace_id"])

    with op.batch_alter_table("replies") as batch:
        batch.alter_column("email_message_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("lead_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("enrollment_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("subject", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("message_id_header", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("in_reply_to", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("raw_body", sa.Text(), nullable=True))
        batch.add_column(sa.Column("match_method", sa.String(length=30), nullable=True))
        batch.add_column(sa.Column("classified_by", sa.String(length=10), nullable=True))
        batch.add_column(sa.Column("classification_confidence", sa.Float(), nullable=True))
        batch.add_column(
            sa.Column("is_auto_reply", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        batch.create_foreign_key(
            "fk_replies_lead",
            "leads",
            ["lead_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_replies_enrollment",
            "campaign_enrollments",
            ["enrollment_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_replies_lead_id", "replies", ["lead_id"])
    op.create_index("ix_replies_message_id_header", "replies", ["message_id_header"])
    op.execute(
        sa.text(
            "UPDATE replies SET "
            "lead_id = (SELECT lead_id FROM email_messages WHERE email_messages.id = "
            "replies.email_message_id), "
            "enrollment_id = (SELECT enrollment_id FROM email_messages WHERE email_messages.id = "
            "replies.email_message_id), "
            "classified_by = 'rule', match_method = 'legacy'",
        ),
    )

    with op.batch_alter_table("suppressions") as batch:
        batch.add_column(sa.Column("reason_code", sa.String(length=30), nullable=True))
        batch.add_column(sa.Column("email_message_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_suppressions_email_message",
            "email_messages",
            ["email_message_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.execute(
        sa.text(
            "UPDATE suppressions SET reason_code = CASE "
            "WHEN reason = 'unsubscribe' THEN 'unsubscribe' ELSE 'manual' END "
            "WHERE reason_code IS NULL",
        ),
    )


def downgrade() -> None:
    with op.batch_alter_table("suppressions") as batch:
        batch.drop_constraint("fk_suppressions_email_message", type_="foreignkey")
        batch.drop_column("email_message_id")
        batch.drop_column("reason_code")
    op.drop_index("ix_replies_message_id_header", table_name="replies")
    op.drop_index("ix_replies_lead_id", table_name="replies")
    op.execute(sa.text("DELETE FROM replies WHERE email_message_id IS NULL"))
    with op.batch_alter_table("replies") as batch:
        batch.drop_constraint("fk_replies_enrollment", type_="foreignkey")
        batch.drop_constraint("fk_replies_lead", type_="foreignkey")
        for column in (
            "is_auto_reply",
            "classification_confidence",
            "classified_by",
            "match_method",
            "raw_body",
            "in_reply_to",
            "message_id_header",
            "subject",
            "enrollment_id",
            "lead_id",
        ):
            batch.drop_column(column)
        batch.alter_column("email_message_id", existing_type=sa.Integer(), nullable=False)
    op.drop_table("inbox_cursors")
    op.drop_table("email_events")
    op.drop_table("webhook_events")
