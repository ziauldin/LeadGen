"""single sign-on: workspace identity providers, verified domains, linked identities

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-10-17 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7f8a9b0c1d2"
down_revision: str | None = "d6e7f8a9b0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BYPASS = "current_setting('app.bypass_rls', true) = 'on'"
OWN = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::integer"
NEW_TENANT_TABLES = ("sso_connections", "verified_domains")


def _workspace_fk() -> sa.Column:
    return sa.Column(
        "workspace_id",
        sa.Integer(),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )


def _timestamps(updated: bool = False) -> list[sa.Column]:
    columns = [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    ]
    if updated:
        columns.append(
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
        )
    return columns


def upgrade() -> None:
    op.create_table(
        "sso_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        _workspace_fk(),
        sa.Column("protocol", sa.String(length=10), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enforce", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_role", sa.String(length=20), nullable=False, server_default="member"),
        sa.Column("oidc_issuer", sa.String(length=500), nullable=True),
        sa.Column("oidc_client_id", sa.String(length=255), nullable=True),
        sa.Column("oidc_client_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("saml_idp_entity_id", sa.String(length=500), nullable=True),
        sa.Column("saml_idp_sso_url", sa.String(length=1000), nullable=True),
        sa.Column("saml_idp_certificate", sa.Text(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(updated=True),
    )
    op.create_index("ix_sso_connections_workspace_id", "sso_connections", ["workspace_id"])

    op.create_table(
        "verified_domains",
        sa.Column("id", sa.Integer(), primary_key=True),
        _workspace_fk(),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("verification_token", sa.String(length=64), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("workspace_id", "domain", name="uq_verified_domains_ws"),
    )
    op.create_index("ix_verified_domains_workspace_id", "verified_domains", ["workspace_id"])
    op.create_index("ix_verified_domains_domain", "verified_domains", ["domain"])

    op.create_table(
        "external_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("provider", "subject", name="uq_external_identities_provider_subject"),
    )
    op.create_index("ix_external_identities_user_id", "external_identities", ["user_id"])

    op.create_table(
        "sso_login_states",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=True),
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("code_verifier", sa.String(length=128), nullable=True),
        sa.Column("next_path", sa.String(length=500), nullable=True),
        sa.Column("link_user_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )

    if op.get_bind().dialect.name == "postgresql":
        for table in NEW_TENANT_TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY tenant_isolation ON {table} "
                f"USING ({BYPASS} OR {OWN}) WITH CHECK ({BYPASS} OR {OWN})",
            )


def downgrade() -> None:
    op.drop_table("sso_login_states")
    op.drop_index("ix_external_identities_user_id", table_name="external_identities")
    op.drop_table("external_identities")
    op.drop_index("ix_verified_domains_domain", table_name="verified_domains")
    op.drop_index("ix_verified_domains_workspace_id", table_name="verified_domains")
    op.drop_table("verified_domains")
    op.drop_index("ix_sso_connections_workspace_id", table_name="sso_connections")
    op.drop_table("sso_connections")
