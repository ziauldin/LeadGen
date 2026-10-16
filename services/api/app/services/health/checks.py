"""Readiness checks used by /health/ready."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings

HEARTBEAT_KEY = "lg:worker:heartbeat"
HEARTBEAT_MAX_AGE_SECONDS = 180
ALEMBIC_INI = Path(__file__).resolve().parents[3] / "alembic.ini"


def _redis() -> redis.Redis:
    return redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)


def check_database(db: Session) -> tuple[bool, str | None]:
    try:
        db.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, exc.__class__.__name__


def check_redis() -> tuple[bool, str | None]:
    try:
        _redis().ping()
        return True, None
    except Exception as exc:
        return False, exc.__class__.__name__


def check_migrations(db: Session) -> tuple[bool, str | None]:
    """The database schema is at the newest Alembic revision this code ships with."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        config = Config(str(ALEMBIC_INI))
        config.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
        heads = set(ScriptDirectory.from_config(config).get_heads())
        current = {row[0] for row in db.execute(text("SELECT version_num FROM alembic_version"))}
    except Exception as exc:
        return False, f"Could not read migration state ({exc.__class__.__name__})"
    if current == heads:
        return True, None
    return False, f"Database at {sorted(current) or 'none'}, code expects {sorted(heads)}"


def record_heartbeat(now: datetime | None = None) -> None:
    moment = (now or datetime.now(UTC)).isoformat()
    _redis().set(HEARTBEAT_KEY, moment, ex=HEARTBEAT_MAX_AGE_SECONDS * 4)


def check_worker_heartbeat(now: datetime | None = None) -> tuple[bool, str | None]:
    """Beat schedules a heartbeat task every minute; a worker running it proves both are up."""
    try:
        raw = _redis().get(HEARTBEAT_KEY)
    except Exception as exc:
        return False, exc.__class__.__name__
    if not raw:
        return False, "No worker heartbeat yet"
    value = raw.decode() if isinstance(raw, bytes) else str(raw)
    try:
        last = datetime.fromisoformat(value)
    except ValueError:
        return False, "Unreadable heartbeat"
    age = ((now or datetime.now(UTC)) - last).total_seconds()
    if age > HEARTBEAT_MAX_AGE_SECONDS:
        return False, f"Last worker heartbeat {int(age)}s ago"
    return True, None
