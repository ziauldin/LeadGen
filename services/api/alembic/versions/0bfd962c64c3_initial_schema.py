"""initial schema

Revision ID: 0bfd962c64c3
Revises:
Create Date: 2026-06-26 05:57:10.310182

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0bfd962c64c3"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("size_estimate", sa.Integer(), nullable=True),
        sa.Column("contact_page_url", sa.String(length=500), nullable=True),
        sa.Column("about_page_url", sa.String(length=500), nullable=True),
        sa.Column("robots_checked", sa.Boolean(), nullable=False),
        sa.Column("enrichment_status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_companies_domain"), "companies", ["domain"], unique=False)
    op.create_index(op.f("ix_companies_name"), "companies", ["name"], unique=False)

    op.create_table(
        "suppressions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_suppressions_domain"), "suppressions", ["domain"], unique=False)
    op.create_index(op.f("ix_suppressions_email"), "suppressions", ["email"], unique=False)

    op.create_table(
        "niches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("industry", sa.String(length=255), nullable=False),
        sa.Column("target_roles", sa.JSON(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("exclusion_keywords", sa.JSON(), nullable=False),
        sa.Column("company_size_min", sa.Integer(), nullable=True),
        sa.Column("company_size_max", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_niches_user_id"), "niches", ["user_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_actor_id"), "audit_logs", ["actor_id"], unique=False)

    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("niche_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("daily_send_limit", sa.Integer(), nullable=False),
        sa.Column("sending_window_start", sa.String(length=5), nullable=True),
        sa.Column("sending_window_end", sa.String(length=5), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_campaigns_niche_id"), "campaigns", ["niche_id"], unique=False)

    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("niche_id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("linkedin_url", sa.String(length=500), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("source_provider", sa.String(length=100), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("qualification_notes", sa.Text(), nullable=True),
        sa.Column("compliance_source_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_leads_company_id"), "leads", ["company_id"], unique=False)
    op.create_index(op.f("ix_leads_linkedin_url"), "leads", ["linkedin_url"], unique=False)
    op.create_index(op.f("ix_leads_niche_id"), "leads", ["niche_id"], unique=False)
    op.create_index(op.f("ix_leads_status"), "leads", ["status"], unique=False)

    op.create_table(
        "search_queries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("niche_id", sa.Integer(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_search_queries_niche_id"), "search_queries", ["niche_id"], unique=False)

    op.create_table(
        "campaign_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("delay_days", sa.Integer(), nullable=False),
        sa.Column("subject_template", sa.String(length=500), nullable=False),
        sa.Column("body_template", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_campaign_steps_campaign_id"), "campaign_steps", ["campaign_id"], unique=False)

    op.create_table(
        "email_contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("email_type", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("is_role_based", sa.Boolean(), nullable=False),
        sa.Column("is_personal", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("opted_out", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_contacts_company_id"), "email_contacts", ["company_id"], unique=False)
    op.create_index(op.f("ix_email_contacts_email"), "email_contacts", ["email"], unique=False)
    op.create_index(op.f("ix_email_contacts_lead_id"), "email_contacts", ["lead_id"], unique=False)

    op.create_table(
        "email_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("reply_status", sa.String(length=50), nullable=False),
        sa.Column("bounce_status", sa.String(length=50), nullable=False),
        sa.Column("unsubscribe_token", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("unsubscribe_token"),
    )
    op.create_index(op.f("ix_email_messages_campaign_id"), "email_messages", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_email_messages_lead_id"), "email_messages", ["lead_id"], unique=False)
    op.create_index(op.f("ix_email_messages_status"), "email_messages", ["status"], unique=False)

    op.create_table(
        "replies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email_message_id", sa.Integer(), nullable=False),
        sa.Column("from_email", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("classification", sa.String(length=50), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["email_message_id"], ["email_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_replies_email_message_id"), "replies", ["email_message_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_replies_email_message_id"), table_name="replies")
    op.drop_table("replies")
    op.drop_index(op.f("ix_email_messages_status"), table_name="email_messages")
    op.drop_index(op.f("ix_email_messages_lead_id"), table_name="email_messages")
    op.drop_index(op.f("ix_email_messages_campaign_id"), table_name="email_messages")
    op.drop_table("email_messages")
    op.drop_index(op.f("ix_email_contacts_lead_id"), table_name="email_contacts")
    op.drop_index(op.f("ix_email_contacts_email"), table_name="email_contacts")
    op.drop_index(op.f("ix_email_contacts_company_id"), table_name="email_contacts")
    op.drop_table("email_contacts")
    op.drop_index(op.f("ix_campaign_steps_campaign_id"), table_name="campaign_steps")
    op.drop_table("campaign_steps")
    op.drop_index(op.f("ix_search_queries_niche_id"), table_name="search_queries")
    op.drop_table("search_queries")
    op.drop_index(op.f("ix_leads_status"), table_name="leads")
    op.drop_index(op.f("ix_leads_niche_id"), table_name="leads")
    op.drop_index(op.f("ix_leads_linkedin_url"), table_name="leads")
    op.drop_index(op.f("ix_leads_company_id"), table_name="leads")
    op.drop_table("leads")
    op.drop_index(op.f("ix_campaigns_niche_id"), table_name="campaigns")
    op.drop_table("campaigns")
    op.drop_index(op.f("ix_audit_logs_actor_id"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index(op.f("ix_niches_user_id"), table_name="niches")
    op.drop_table("niches")
    op.drop_index(op.f("ix_suppressions_email"), table_name="suppressions")
    op.drop_index(op.f("ix_suppressions_domain"), table_name="suppressions")
    op.drop_table("suppressions")
    op.drop_index(op.f("ix_companies_name"), table_name="companies")
    op.drop_index(op.f("ix_companies_domain"), table_name="companies")
    op.drop_table("companies")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
