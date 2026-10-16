"""row-level security on tenant tables (PostgreSQL)

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-10-17 12:00:00.000000

Defence in depth behind the ORM workspace filters: PostgreSQL itself refuses to return or
write another workspace's rows. The app sets two transaction-local settings:

* ``app.workspace_id``: the workspace the session is scoped to;
* ``app.bypass_rls = 'on'``: for explicit cross-tenant system work (dispatcher, webhooks,
  migrations).

A session with neither sees no tenant rows. ``FORCE`` applies the policies to the table owner
too (the app usually connects as the owner); superusers always bypass RLS.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c5d6e7f8a9b0"
down_revision: str | None = "b4c5d6e7f8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "campaign_enrollments",
    "campaign_steps",
    "campaigns",
    "companies",
    "email_contacts",
    "email_events",
    "email_messages",
    "email_templates",
    "inbox_cursors",
    "leads",
    "llm_usage",
    "niches",
    "provider_credentials",
    "replies",
    "search_queries",
    "webhook_events",
)
BYPASS = "current_setting('app.bypass_rls', true) = 'on'"
OWN = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::integer"


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({BYPASS} OR {OWN}) WITH CHECK ({BYPASS} OR {OWN})",
        )
    # Suppressions with no workspace are platform-wide (hard bounces, complaints) and must be
    # visible to, and writable from, every workspace.
    op.execute("ALTER TABLE suppressions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE suppressions FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON suppressions "
        f"USING ({BYPASS} OR workspace_id IS NULL OR {OWN}) "
        f"WITH CHECK ({BYPASS} OR workspace_id IS NULL OR {OWN})",
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in (*TENANT_TABLES, "suppressions"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
