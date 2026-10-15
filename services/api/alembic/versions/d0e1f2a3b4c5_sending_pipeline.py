"""sending pipeline: message states/tracking, campaign scheduling, warm-up, webhook tokens

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-10-16 12:00:00.000000

Existing messages: ``recipient_domain`` is filled in, and messages that were marked FAILED
only because the old gate refused them (window/limit) are returned to APPROVED.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: str | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MESSAGE_COLUMNS = [
    ("recipient_domain", sa.String(length=255)),
    ("scheduled_for", sa.DateTime(timezone=True)),
    ("next_attempt_at", sa.DateTime(timezone=True)),
    ("queued_at", sa.DateTime(timezone=True)),
    ("sending_started_at", sa.DateTime(timezone=True)),
    ("last_error", sa.Text()),
    ("failure_reason", sa.String(length=255)),
    ("idempotency_key", sa.String(length=64)),
    ("rfc_message_id", sa.String(length=255)),
    ("reply_token", sa.String(length=64)),
    ("approved_at", sa.DateTime(timezone=True)),
    ("rejected_reason", sa.String(length=500)),
    ("edited_at", sa.DateTime(timezone=True)),
    ("generation_mode", sa.String(length=20)),
    ("template_id", sa.String(length=100)),
    ("llm_model", sa.String(length=100)),
    ("prompt_version", sa.String(length=20)),
]


def upgrade() -> None:
    with op.batch_alter_table("email_messages") as batch:
        for name, type_ in MESSAGE_COLUMNS:
            batch.add_column(sa.Column(name, type_, nullable=True))
        batch.add_column(
            sa.Column("send_attempts", sa.Integer(), nullable=False, server_default="0"),
        )
        batch.add_column(sa.Column("sender_credential_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("approved_by", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("edited_by", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        batch.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        batch.create_foreign_key(
            "fk_email_messages_sender_credential",
            "provider_credentials",
            ["sender_credential_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_email_messages_approved_by",
            "users",
            ["approved_by"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_email_messages_edited_by",
            "users",
            ["edited_by"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_unique_constraint("uq_email_messages_idempotency_key", ["idempotency_key"])
        batch.create_unique_constraint("uq_email_messages_reply_token", ["reply_token"])
    for column in ("recipient_domain", "next_attempt_at", "rfc_message_id", "provider_message_id"):
        op.create_index(f"ix_email_messages_{column}", "email_messages", [column])

    with op.batch_alter_table("campaigns") as batch:
        batch.add_column(sa.Column("timezone", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("sending_days", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("per_domain_limit", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("sender_credential_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("stop_on_reply", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
        batch.add_column(sa.Column("auto_paused_reason", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key(
            "fk_campaigns_sender_credential",
            "provider_credentials",
            ["sender_credential_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("provider_credentials") as batch:
        batch.add_column(
            sa.Column("warmup_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        batch.add_column(sa.Column("warmup_started_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column("warmup_start_volume", sa.Integer(), nullable=False, server_default="10"),
        )
        batch.add_column(
            sa.Column("warmup_daily_increment", sa.Integer(), nullable=False, server_default="5"),
        )
        batch.add_column(sa.Column("warmup_max", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("webhook_token", sa.String(length=64), nullable=True))
        batch.create_unique_constraint("uq_provider_credentials_webhook_token", ["webhook_token"])

    # Backfill: recipient domains, and undo failures caused by the old timing gate.
    op.execute(
        sa.text(
            "UPDATE email_messages SET recipient_domain = "
            "LOWER(SUBSTR(recipient_email, INSTR(recipient_email, '@') + 1)) "
            "WHERE recipient_email LIKE '%@%'",
        )
        if op.get_bind().dialect.name == "sqlite"
        else sa.text(
            "UPDATE email_messages SET recipient_domain = "
            "LOWER(SPLIT_PART(recipient_email, '@', 2)) WHERE recipient_email LIKE '%@%'",
        ),
    )
    op.execute(
        sa.text(
            "UPDATE email_messages SET status = 'approved' WHERE status = 'failed' "
            "AND sent_at IS NULL AND provider_message_id IS NULL",
        ),
    )


def downgrade() -> None:
    with op.batch_alter_table("provider_credentials") as batch:
        batch.drop_constraint("uq_provider_credentials_webhook_token", type_="unique")
        for column in (
            "webhook_token",
            "warmup_max",
            "warmup_daily_increment",
            "warmup_start_volume",
            "warmup_started_at",
            "warmup_enabled",
        ):
            batch.drop_column(column)
    with op.batch_alter_table("campaigns") as batch:
        batch.drop_constraint("fk_campaigns_sender_credential", type_="foreignkey")
        for column in (
            "completed_at",
            "auto_paused_reason",
            "stop_on_reply",
            "sender_credential_id",
            "per_domain_limit",
            "sending_days",
            "timezone",
        ):
            batch.drop_column(column)
    for column in ("recipient_domain", "next_attempt_at", "rfc_message_id", "provider_message_id"):
        op.drop_index(f"ix_email_messages_{column}", table_name="email_messages")
    with op.batch_alter_table("email_messages") as batch:
        batch.drop_constraint("uq_email_messages_reply_token", type_="unique")
        batch.drop_constraint("uq_email_messages_idempotency_key", type_="unique")
        batch.drop_constraint("fk_email_messages_edited_by", type_="foreignkey")
        batch.drop_constraint("fk_email_messages_approved_by", type_="foreignkey")
        batch.drop_constraint("fk_email_messages_sender_credential", type_="foreignkey")
        for column in (
            "updated_at",
            "created_at",
            "edited_by",
            "approved_by",
            "sender_credential_id",
            "send_attempts",
            *[name for name, _ in reversed(MESSAGE_COLUMNS)],
        ):
            batch.drop_column(column)
