from sqlalchemy import text
from sqlalchemy.orm import Session

import redis

from app.core.config import settings


def check_database(db: Session) -> tuple[bool, str | None]:
    try:
        db.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def check_redis() -> tuple[bool, str | None]:
    try:
        client = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        client.ping()
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
