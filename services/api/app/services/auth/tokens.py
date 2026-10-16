"""Refresh-token rotation and single-use email action tokens.

Only SHA-256 hashes of tokens are stored. Refresh tokens rotate on every use; presenting a
token that was already rotated (a replay) revokes the whole family, which logs out an attacker
who stole an old token as well as the legitimate session.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AuthenticationError, ValidationFailedError
from app.models.auth_tokens import EmailActionToken, RefreshToken
from app.models.user import User

PURPOSE_VERIFY = "verify"
PURPOSE_RESET = "reset"
EMAIL_TOKEN_TTL = {
    PURPOSE_VERIFY: timedelta(hours=48),
    PURPOSE_RESET: timedelta(hours=1),
}


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _as_aware(value: datetime) -> datetime:
    # SQLite returns naive datetimes; Postgres returns aware ones.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def issue_refresh_token(
    db: Session,
    user: User,
    *,
    family_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, RefreshToken]:
    raw = secrets.token_urlsafe(48)
    token = RefreshToken(
        user_id=user.id,
        family_id=family_id or secrets.token_hex(16),
        token_hash=hash_token(raw),
        expires_at=_now() + timedelta(days=settings.jwt_refresh_token_expire_days),
        created_ip=ip,
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(token)
    db.flush()
    return raw, token


def revoke_family(db: Session, family_id: str) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now()),
    )


def revoke_all_for_user(db: Session, user_id: int) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now()),
    )


def rotate_refresh_token(
    db: Session,
    raw: str,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, str]:
    """Exchange a refresh token for a new one. Raises ``AuthenticationError`` if invalid."""
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
    if token is None:
        raise AuthenticationError("Session expired. Please sign in again.")

    if token.revoked_at is not None:
        # Replay of an already-rotated token: assume theft and end the whole session family.
        revoke_family(db, token.family_id)
        db.commit()
        raise AuthenticationError("Session expired. Please sign in again.")

    if _as_aware(token.expires_at) <= _now():
        raise AuthenticationError("Session expired. Please sign in again.")

    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Session expired. Please sign in again.")

    new_raw, new_token = issue_refresh_token(
        db,
        user,
        family_id=token.family_id,
        ip=ip,
        user_agent=user_agent,
    )
    token.revoked_at = _now()
    token.replaced_by_id = new_token.id
    db.commit()
    return user, new_raw


def revoke_refresh_token(db: Session, raw: str) -> None:
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
    if token is not None:
        revoke_family(db, token.family_id)
        db.commit()


def create_email_action_token(db: Session, user: User, purpose: str) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(
        EmailActionToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=hash_token(raw),
            expires_at=_now() + EMAIL_TOKEN_TTL[purpose],
        ),
    )
    db.flush()
    return raw


def consume_email_action_token(db: Session, raw: str, purpose: str) -> User:
    token = db.scalar(
        select(EmailActionToken).where(
            EmailActionToken.token_hash == hash_token(raw),
            EmailActionToken.purpose == purpose,
        ),
    )
    if token is None or token.used_at is not None or _as_aware(token.expires_at) <= _now():
        raise ValidationFailedError("This link is invalid or has expired")
    user = db.get(User, token.user_id)
    if user is None:
        raise ValidationFailedError("This link is invalid or has expired")
    token.used_at = _now()
    return user
