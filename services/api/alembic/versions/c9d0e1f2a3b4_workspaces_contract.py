"""workspaces (contract): NOT NULL, foreign keys, indexes and per-workspace unique keys

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-10-16 10:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REQUIRED = (
    "niches",
    "search_queries",
    "leads",
    "companies",
    "email_contacts",
    "campaigns",
    "campaign_steps",
    "email_messages",
    "replies",
    "provider_credentials",
)
OPTIONAL = ("suppressions", "audit_logs")  # NULL = platform-wide


def upgrade() -> None:
    for table in REQUIRED + OPTIONAL:
        with op.batch_alter_table(table) as batch:
            if table in REQUIRED:
                batch.alter_column("workspace_id", existing_type=sa.Integer(), nullable=False)
            batch.create_foreign_key(
                f"fk_{table}_workspace_id",
                "workspaces",
                ["workspace_id"],
                ["id"],
                ondelete="CASCADE",
            )
        op.create_index(f"ix_{table}_workspace_id", table, ["workspace_id"])

    with op.batch_alter_table("provider_credentials") as batch:
        batch.drop_constraint("uq_user_provider", type_="unique")
        batch.create_unique_constraint(
            "uq_workspace_provider",
            ["workspace_id", "provider_type", "provider_name"],
        )
    with op.batch_alter_table("leads") as batch:
        batch.create_unique_constraint(
            "uq_leads_workspace_niche_linkedin",
            ["workspace_id", "niche_id", "linkedin_url"],
        )
    with op.batch_alter_table("companies") as batch:
        batch.create_unique_constraint("uq_companies_workspace_domain", ["workspace_id", "domain"])
    with op.batch_alter_table("email_contacts") as batch:
        batch.create_unique_constraint(
            "uq_email_contacts_workspace_lead_email",
            ["workspace_id", "lead_id", "email"],
        )

    # Creator columns: a member leaving must not delete the workspace's niches/credentials.
    bind = op.get_bind()
    for table in ("niches", "provider_credentials"):
        if bind.dialect.name == "postgresql":
            op.drop_constraint(f"{table}_user_id_fkey", table, type_="foreignkey")
            op.alter_column(table, "user_id", existing_type=sa.Integer(), nullable=True)
            op.create_foreign_key(
                f"fk_{table}_user_id",
                table,
                "users",
                ["user_id"],
                ["id"],
                ondelete="SET NULL",
            )
        else:
            # SQLite foreign keys from earlier migrations are unnamed; a naming convention
            # lets batch mode find and replace them.
            with op.batch_alter_table(
                table,
                naming_convention={"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"},
            ) as batch:
                batch.drop_constraint(f"fk_{table}_user_id_users", type_="foreignkey")
                batch.alter_column("user_id", existing_type=sa.Integer(), nullable=True)
                batch.create_foreign_key(
                    f"fk_{table}_user_id",
                    "users",
                    ["user_id"],
                    ["id"],
                    ondelete="SET NULL",
                )

    with op.batch_alter_table("users") as batch:
        batch.create_foreign_key(
            "fk_users_last_workspace",
            "workspaces",
            ["last_workspace_id"],
            ["id"],
            ondelete="SET NULL",
        )
    with op.batch_alter_table("workspaces") as batch:
        batch.create_foreign_key(
            "fk_workspaces_created_by",
            "users",
            ["created_by"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("workspaces") as batch:
        batch.drop_constraint("fk_workspaces_created_by", type_="foreignkey")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("fk_users_last_workspace", type_="foreignkey")
    with op.batch_alter_table("email_contacts") as batch:
        batch.drop_constraint("uq_email_contacts_workspace_lead_email", type_="unique")
    with op.batch_alter_table("companies") as batch:
        batch.drop_constraint("uq_companies_workspace_domain", type_="unique")
    with op.batch_alter_table("leads") as batch:
        batch.drop_constraint("uq_leads_workspace_niche_linkedin", type_="unique")
    with op.batch_alter_table("provider_credentials") as batch:
        batch.drop_constraint("uq_workspace_provider", type_="unique")
        batch.create_unique_constraint(
            "uq_user_provider",
            ["user_id", "provider_type", "provider_name"],
        )
    for table in reversed(REQUIRED + OPTIONAL):
        op.drop_index(f"ix_{table}_workspace_id", table_name=table)
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"fk_{table}_workspace_id", type_="foreignkey")
            if table in REQUIRED:
                batch.alter_column("workspace_id", existing_type=sa.Integer(), nullable=True)
