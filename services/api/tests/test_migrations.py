"""Migration tests: legacy single-user data is moved into workspaces correctly.

Runs on SQLite by default; set TEST_DATABASE_URL to a disposable PostgreSQL database to run the
same checks against Postgres (CI does this).
"""

import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from app.core.config import normalize_database_url

API_ROOT = Path(__file__).resolve().parents[1]
PRE_WORKSPACES = "e5f6a7b8c9d0"


def _config(url: str) -> Config:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    cfg.attributes["database_url"] = url
    return cfg


@pytest.fixture
def database_url(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        url = normalize_database_url(url)
        engine = sa.create_engine(url)
        with engine.begin() as conn:
            conn.exec_driver_sql("DROP SCHEMA public CASCADE")
            conn.exec_driver_sql("CREATE SCHEMA public")
        engine.dispose()
        return url
    return f"sqlite:///{(tmp_path / 'migrations.db').as_posix()}"


def _seed_legacy(engine: sa.Engine) -> None:
    with engine.begin() as conn:
        x = conn.exec_driver_sql
        x(
            "INSERT INTO users (id, name, email, hashed_password, role) VALUES "
            "(1, 'Alice Owner', 'alice@example.com', 'h', 'operator'), "
            "(2, 'Bob Other', 'bob@example.com', 'h', 'operator')",
        )
        x(
            "INSERT INTO user_settings (user_id, sender_name, sender_company, business_address) "
            "VALUES (1, 'Alice', 'Alice Co', '1 High St')",
        )
        x(
            "INSERT INTO niches (id, user_id, name, country, industry, target_roles, keywords, "
            "exclusion_keywords) VALUES "
            "(1, 1, 'A niche', 'UK', 'Legal', '[]', '[]', '[]'), "
            "(2, 2, 'B niche', 'UK', 'Legal', '[]', '[]', '[]')",
        )
        # One company shared by both users' leads.
        x(
            "INSERT INTO companies (id, name, website, domain, robots_checked, enrichment_status) "
            "VALUES (1, 'Shared Ltd', 'https://shared.co.uk', 'shared.co.uk', FALSE, 'completed'), "
            "(2, 'Orphan Ltd', NULL, NULL, FALSE, 'pending')",
        )
        x(
            "INSERT INTO leads (id, niche_id, full_name, company_id, status, score) VALUES "
            "(1, 1, 'Lead A', 1, 'new', 0), (2, 2, 'Lead B', 1, 'new', 0)",
        )
        x(
            "INSERT INTO email_contacts (id, lead_id, company_id, email, email_type, confidence, "
            "is_role_based, is_personal, is_verified, opted_out) VALUES "
            "(1, 1, 1, 'a@shared.co.uk', 'named', 0.8, FALSE, TRUE, FALSE, FALSE), "
            "(2, 2, 1, 'b@shared.co.uk', 'named', 0.8, FALSE, TRUE, FALSE, FALSE), "
            "(3, NULL, 1, 'info@shared.co.uk', 'generic', 0.5, FALSE, FALSE, FALSE, FALSE)",
        )
        x(
            "INSERT INTO campaigns (id, niche_id, name, status, daily_send_limit) VALUES "
            "(1, 1, 'A campaign', 'draft', 20)",
        )
        x(
            "INSERT INTO campaign_steps (campaign_id, step_number, delay_days, subject_template, "
            "body_template) VALUES (1, 1, 0, 'Hi', 'Body')",
        )
        x(
            "INSERT INTO email_messages (id, campaign_id, lead_id, recipient_email, subject, body, "
            "status, reply_status, bounce_status, unsubscribe_token) VALUES "
            "(1, 1, 1, 'a@shared.co.uk', 'Hi', 'Body', 'sent', 'none', 'none', 'tok1')",
        )
        x(
            "INSERT INTO replies (email_message_id, from_email, body, classification, received_at) "
            "VALUES (1, 'a@shared.co.uk', 'Thanks', 'positive', CURRENT_TIMESTAMP)",
        )
        # Old global suppressions: an unsubscribe that wrongly stored the domain, and a
        # manual domain block.
        x(
            "INSERT INTO suppressions (email, domain, reason, source) VALUES "
            "('gone@gmail.com', 'gmail.com', 'unsubscribe', 'unsubscribe_link'), "
            "(NULL, 'blocked.example', 'manual', 'manual')",
        )
        if engine.dialect.name == "postgresql":
            # Explicit ids above don't advance PostgreSQL sequences; real data would have.
            for table in (
                "users",
                "niches",
                "companies",
                "leads",
                "email_contacts",
                "campaigns",
                "campaign_steps",
                "email_messages",
                "replies",
                "suppressions",
                "user_settings",
            ):
                x(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)",
                )


def test_upgrade_moves_legacy_data_into_workspaces(database_url):
    cfg = _config(database_url)
    command.upgrade(cfg, PRE_WORKSPACES)
    engine = sa.create_engine(database_url)
    _seed_legacy(engine)

    command.upgrade(cfg, "head")

    with engine.connect() as conn:
        q = lambda sql: conn.exec_driver_sql(sql).all()  # noqa: E731

        workspaces = q("SELECT id, created_by FROM workspaces ORDER BY created_by")
        assert len(workspaces) == 2
        ws_a, ws_b = workspaces[0][0], workspaces[1][0]

        assert q("SELECT workspace_id, user_id, role FROM workspace_members ORDER BY user_id") == [
            (ws_a, 1, "owner"),
            (ws_b, 2, "owner"),
        ]
        assert q("SELECT last_workspace_id FROM users ORDER BY id") == [(ws_a,), (ws_b,)]
        assert q(
            f"SELECT sender_company, business_address FROM workspace_settings WHERE workspace_id = {ws_a}"
        ) == [
            ("Alice Co", "1 High St"),
        ]

        assert q("SELECT id, workspace_id FROM niches ORDER BY id") == [(1, ws_a), (2, ws_b)]
        assert q("SELECT workspace_id FROM campaigns") == [(ws_a,)]
        assert q("SELECT workspace_id FROM campaign_steps") == [(ws_a,)]
        assert q("SELECT workspace_id FROM email_messages") == [(ws_a,)]
        assert q("SELECT workspace_id FROM replies") == [(ws_a,)]

        # The shared company was split: each workspace has its own copy.
        shared = q(
            "SELECT id, workspace_id FROM companies WHERE domain = 'shared.co.uk' ORDER BY workspace_id"
        )
        assert [row[1] for row in shared] == [ws_a, ws_b]
        company_for = {row[1]: row[0] for row in shared}
        assert q("SELECT id, workspace_id, company_id FROM leads ORDER BY id") == [
            (1, ws_a, company_for[ws_a]),
            (2, ws_b, company_for[ws_b]),
        ]
        contacts = q(
            "SELECT email, workspace_id, company_id FROM email_contacts ORDER BY email, workspace_id"
        )
        assert ("a@shared.co.uk", ws_a, company_for[ws_a]) in contacts
        assert ("b@shared.co.uk", ws_b, company_for[ws_b]) in contacts
        # The company-level contact exists once per copy.
        assert ("info@shared.co.uk", ws_a, company_for[ws_a]) in contacts
        assert ("info@shared.co.uk", ws_b, company_for[ws_b]) in contacts
        # A company nobody used goes to the oldest user's workspace.
        assert q("SELECT workspace_id FROM companies WHERE name = 'Orphan Ltd'") == [(ws_a,)]

        # Suppressions copied into every workspace; unsubscribes no longer block the domain.
        suppressions = q(
            "SELECT workspace_id, email, domain FROM suppressions ORDER BY workspace_id, domain"
        )
        assert (ws_a, "gone@gmail.com", None) in suppressions
        assert (ws_b, "gone@gmail.com", None) in suppressions
        assert (ws_a, None, "blocked.example") in suppressions
        assert q("SELECT COUNT(*) FROM suppressions WHERE workspace_id IS NULL") == [(0,)]

        # Pre-existing accounts count as verified.
        assert q("SELECT COUNT(*) FROM users WHERE email_verified_at IS NULL") == [(0,)]

    engine.dispose()


def test_models_match_migrations(database_url):
    """`alembic check` fails if the models and the migrations have drifted apart."""
    cfg = _config(database_url)
    command.upgrade(cfg, "head")
    command.check(cfg)
