"""sequences: campaign enrollments, step links on messages, step options

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-10-16 13:00:00.000000

Backfill: one enrollment per existing (campaign, lead) message pair; their messages become
step 1. Enrollments whose email was already sent start at step 1 with no next step, so the
completion job closes them out (existing campaigns only had one usable step).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "d0e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaign_enrollments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            sa.Integer(),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            sa.Integer(),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_step_number", sa.Integer(), nullable=True),
        sa.Column("next_send_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_reason", sa.String(length=255), nullable=True),
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
        sa.UniqueConstraint("campaign_id", "lead_id", name="uq_campaign_enrollments_campaign_lead"),
    )
    for column in (
        "workspace_id",
        "campaign_id",
        "lead_id",
        "recipient_email",
        "status",
        "next_send_at",
    ):
        op.create_index(f"ix_campaign_enrollments_{column}", "campaign_enrollments", [column])

    with op.batch_alter_table("email_messages") as batch:
        batch.add_column(sa.Column("enrollment_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("campaign_step_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("step_number", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_email_messages_enrollment",
            "campaign_enrollments",
            ["enrollment_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_email_messages_campaign_step",
            "campaign_steps",
            ["campaign_step_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_email_messages_enrollment_id", "email_messages", ["enrollment_id"])

    # Duplicate step numbers would break the new unique constraint: keep the first.
    op.execute(
        sa.text(
            "DELETE FROM campaign_steps WHERE id NOT IN (SELECT keep_id FROM ("
            "SELECT MIN(id) AS keep_id FROM campaign_steps GROUP BY campaign_id, step_number"
            ") AS keepers)",
        ),
    )
    with op.batch_alter_table("campaign_steps") as batch:
        batch.add_column(sa.Column("template_id", sa.String(length=100), nullable=True))
        batch.add_column(
            sa.Column("use_ai", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        batch.add_column(sa.Column("ai_instructions", sa.String(length=2000), nullable=True))
        batch.add_column(
            sa.Column(
                "thread_with_previous",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )
        batch.create_unique_constraint(
            "uq_campaign_steps_campaign_step",
            ["campaign_id", "step_number"],
        )

    # Backfill enrollments from existing campaign messages.
    conn = op.get_bind()
    pairs = conn.execute(
        sa.text(
            "SELECT workspace_id, campaign_id, lead_id, MIN(recipient_email), "
            "MAX(CASE WHEN status IN ('sent', 'bounced', 'complained') THEN 1 ELSE 0 END), "
            "MAX(sent_at) "
            "FROM email_messages WHERE campaign_id IS NOT NULL "
            "GROUP BY workspace_id, campaign_id, lead_id",
        ),
    ).all()
    for workspace_id, campaign_id, lead_id, recipient, any_sent, last_sent in pairs:
        conn.execute(
            sa.text(
                "INSERT INTO campaign_enrollments (workspace_id, campaign_id, lead_id, "
                "recipient_email, status, current_step, next_step_number, last_sent_at) "
                "VALUES (:ws, :cid, :lid, :email, 'active', :current, :next, :last)",
            ),
            {
                "ws": workspace_id,
                "cid": campaign_id,
                "lid": lead_id,
                "email": recipient,
                "current": 1 if any_sent else 0,
                "next": None if any_sent else 1,
                "last": last_sent,
            },
        )
        enrollment_id = conn.execute(
            sa.text(
                "SELECT id FROM campaign_enrollments WHERE campaign_id = :cid AND lead_id = :lid",
            ),
            {"cid": campaign_id, "lid": lead_id},
        ).scalar_one()
        first_message = conn.execute(
            sa.text(
                "SELECT MIN(id) FROM email_messages WHERE campaign_id = :cid AND lead_id = :lid",
            ),
            {"cid": campaign_id, "lid": lead_id},
        ).scalar_one()
        conn.execute(
            sa.text(
                "UPDATE email_messages SET enrollment_id = :eid, step_number = 1 WHERE id = :mid",
            ),
            {"eid": enrollment_id, "mid": first_message},
        )

    with op.batch_alter_table("email_messages") as batch:
        batch.create_unique_constraint(
            "uq_email_messages_enrollment_step",
            ["enrollment_id", "step_number"],
        )


def downgrade() -> None:
    with op.batch_alter_table("email_messages") as batch:
        batch.drop_constraint("uq_email_messages_enrollment_step", type_="unique")
    op.drop_index("ix_email_messages_enrollment_id", table_name="email_messages")
    with op.batch_alter_table("email_messages") as batch:
        batch.drop_constraint("fk_email_messages_campaign_step", type_="foreignkey")
        batch.drop_constraint("fk_email_messages_enrollment", type_="foreignkey")
        batch.drop_column("step_number")
        batch.drop_column("campaign_step_id")
        batch.drop_column("enrollment_id")
    with op.batch_alter_table("campaign_steps") as batch:
        batch.drop_constraint("uq_campaign_steps_campaign_step", type_="unique")
        batch.drop_column("thread_with_previous")
        batch.drop_column("ai_instructions")
        batch.drop_column("use_ai")
        batch.drop_column("template_id")
    op.drop_table("campaign_enrollments")
