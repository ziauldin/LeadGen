"""PostgreSQL row-level security. Runs only with TEST_DATABASE_URL pointing at PostgreSQL,
connected as a non-superuser (superusers always bypass RLS)."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.core.tenancy import bind_session, system_session
from app.models.company import Company
from tests.conftest import (
    IS_POSTGRES,
    AppSessionLocal,
    TestingSessionLocal,
    auth_headers,
    engine,
    get_client,
)
from tests.test_approvals import drafts

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not IS_POSTGRES, reason="row-level security is PostgreSQL-only"),
]


@pytest.fixture(autouse=True)
def _require_non_superuser():
    with engine.connect() as conn:
        if conn.exec_driver_sql(
            "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
        ).scalar():
            pytest.skip("connected as a superuser, which bypasses row-level security")


def _two_workspaces():
    client = get_client()
    drafts(client, 2)  # workspace 1, with companies and leads
    other = auth_headers(client, email="other@rls-test.co.uk")
    client.post(
        "/niches",
        headers=other,
        json={"name": "Theirs", "country": "UK", "industry": "Legal", "target_roles": ["X"]},
    )
    db = TestingSessionLocal()
    try:
        ids = sorted({row[0] for row in db.execute(text("SELECT id FROM workspaces"))})
    finally:
        db.close()
    return ids


def test_raw_sql_only_sees_the_bound_workspace():
    _first, second = _two_workspaces()
    db = AppSessionLocal()
    try:
        bind_session(db, second)
        # A hand-written query with no workspace filter still can't see workspace 1's rows.
        workspaces = {
            row[0] for row in db.execute(text("SELECT DISTINCT workspace_id FROM niches"))
        }
        assert workspaces == {second}
        assert db.execute(text("SELECT count(*) FROM companies")).scalar() == 0
    finally:
        db.close()


def test_unscoped_sessions_see_no_tenant_rows_and_system_sessions_see_all():
    first, second = _two_workspaces()
    db = AppSessionLocal()
    try:
        assert db.execute(text("SELECT count(*) FROM niches")).scalar() == 0
        db.rollback()
        with system_session(db):
            seen = {row[0] for row in db.execute(text("SELECT DISTINCT workspace_id FROM niches"))}
        assert seen == {first, second}
    finally:
        db.close()


def test_writes_into_another_workspace_are_refused():
    first, second = _two_workspaces()
    db = AppSessionLocal()
    try:
        bind_session(db, second)
        with pytest.raises(ProgrammingError, match="row-level security"):
            db.execute(
                text(
                    "INSERT INTO niches (workspace_id, name, country, industry, target_roles, "
                    "keywords, exclusion_keywords) VALUES (:ws, 'x', 'UK', 'x', '[]', '[]', '[]')"
                ),
                {"ws": first},
            )
    finally:
        db.rollback()
        db.close()


def test_background_enrichment_runs_under_rls(monkeypatch):
    client = get_client()
    drafts(client, 1)
    db = TestingSessionLocal()
    try:
        company_id = db.query(Company.id).first()[0]
    finally:
        db.close()

    from app.workers import enrichment_jobs

    monkeypatch.setattr(
        enrichment_jobs,
        "enrich_company_record",
        lambda session, cid: session.get(Company, cid),
    )
    result = enrichment_jobs.enrich_company.run(company_id)
    assert result["status"] != "missing"
