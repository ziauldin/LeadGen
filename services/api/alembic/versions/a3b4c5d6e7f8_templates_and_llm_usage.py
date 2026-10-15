"""templates and llm usage: workspace email templates, per-call LLM usage

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-10-16 18:00:00.000000

Messages that used the old built-in "wellpredict" template now point at the neutral system
template, which renders the same variables.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: str | None = "f2a3b4c5d6e7"
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
        "email_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        _workspace_fk(),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_email_templates_workspace_id", "email_templates", ["workspace_id"])

    op.create_table(
        "llm_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        _workspace_fk(),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "email_message_id",
            sa.Integer(),
            sa.ForeignKey("email_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("key_source", sa.String(length=20), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("succeeded", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_llm_usage_workspace_id", "llm_usage", ["workspace_id"])
    op.create_index("ix_llm_usage_created_at", "llm_usage", ["created_at"])

    with op.batch_alter_table("email_messages") as batch:
        batch.add_column(sa.Column("generation_note", sa.String(length=500), nullable=True))

    for table in ("email_messages", "campaign_steps"):
        op.execute(
            sa.text(
                f"UPDATE {table} SET template_id = 'system:intro' "  # noqa: S608 - fixed names
                "WHERE template_id IN ('wellpredict', 'default')",
            ),
        )


def downgrade() -> None:
    with op.batch_alter_table("email_messages") as batch:
        batch.drop_column("generation_note")
    op.drop_index("ix_llm_usage_created_at", table_name="llm_usage")
    op.drop_index("ix_llm_usage_workspace_id", table_name="llm_usage")
    op.drop_table("llm_usage")
    op.drop_index("ix_email_templates_workspace_id", table_name="email_templates")
    op.drop_table("email_templates")
