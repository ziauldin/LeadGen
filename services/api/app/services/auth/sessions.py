"""Active sessions: one per refresh-token family (a device or browser signed in)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.auth_tokens import RefreshToken
from app.services.auth.tokens import hash_token, revoke_family


@dataclass
class ActiveSession:
    id: str
    signed_in_at: datetime
    last_active_at: datetime
    ip: str | None
    user_agent: str | None
    current: bool


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def family_of(db: Session, raw_refresh_token: str | None) -> str | None:
    if not raw_refresh_token:
        return None
    return db.scalar(
        select(RefreshToken.family_id).where(
            RefreshToken.token_hash == hash_token(raw_refresh_token)
        )
    )


def list_sessions(db: Session, user_id: int, *, current_family: str | None) -> list[ActiveSession]:
    now = datetime.now(UTC)
    tokens = db.scalars(
        select(RefreshToken)
        .where(RefreshToken.user_id == user_id)
        .order_by(RefreshToken.created_at.asc(), RefreshToken.id.asc())
    ).all()
    families: dict[str, list[RefreshToken]] = {}
    for token in tokens:
        families.setdefault(token.family_id, []).append(token)
    sessions = []
    for family_id, chain in families.items():
        latest = chain[-1]
        if latest.revoked_at is not None or _aware(latest.expires_at) <= now:
            continue
        sessions.append(
            ActiveSession(
                id=family_id,
                signed_in_at=_aware(chain[0].created_at),
                last_active_at=_aware(latest.created_at),
                ip=latest.created_ip,
                user_agent=latest.user_agent,
                current=family_id == current_family,
            ),
        )
    return sorted(sessions, key=lambda s: s.last_active_at, reverse=True)


def revoke_session(db: Session, user_id: int, family_id: str) -> None:
    owned = db.scalar(
        select(RefreshToken.id)
        .where(RefreshToken.user_id == user_id, RefreshToken.family_id == family_id)
        .limit(1)
    )
    if owned is None:
        raise NotFoundError("Session not found")
    revoke_family(db, family_id)
    db.commit()
