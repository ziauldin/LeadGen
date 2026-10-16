from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.services.health import checks
from tests.conftest import TestingSessionLocal


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    def set(self, key, value, ex=None):
        self.store[key] = value

    def get(self, key):
        value = self.store.get(key)
        return value.encode() if value else None

    def ping(self):
        return True


def test_heartbeat_fresh_stale_and_missing(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(checks, "_redis", lambda: fake)
    assert checks.check_worker_heartbeat() == (False, "No worker heartbeat yet")

    now = datetime.now(UTC)
    checks.record_heartbeat(now)
    assert checks.check_worker_heartbeat(now + timedelta(seconds=30)) == (True, None)
    ok, detail = checks.check_worker_heartbeat(now + timedelta(minutes=10))
    assert not ok and "600s ago" in detail


def test_heartbeat_task_records_through_celery(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(checks, "_redis", lambda: fake)
    from app.workers.ops_jobs import heartbeat

    heartbeat.delay()
    assert checks.HEARTBEAT_KEY in fake.store


def test_migration_check_compares_with_alembic_head():
    db = TestingSessionLocal()
    try:
        db.execute(text("DROP TABLE IF EXISTS alembic_version"))
        db.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        db.execute(text("INSERT INTO alembic_version VALUES ('0000old')"))
        ok, detail = checks.check_migrations(db)
        assert not ok and "0000old" in detail

        from alembic.config import Config
        from alembic.script import ScriptDirectory

        head = ScriptDirectory.from_config(Config(str(checks.ALEMBIC_INI))).get_current_head()
        db.execute(text("UPDATE alembic_version SET version_num = :v"), {"v": head})
        assert checks.check_migrations(db) == (True, None)
    finally:
        db.execute(text("DROP TABLE IF EXISTS alembic_version"))
        db.commit()
        db.close()
