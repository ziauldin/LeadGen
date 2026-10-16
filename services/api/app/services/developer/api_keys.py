"""Workspace API keys: generated once, stored as a hash, limited by scopes."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailedError
from app.core.permissions import Permission
from app.core.tenancy import system_session
from app.models.developer import ApiKey

KEY_PREFIX = "lg_live_"
PREFIX_LENGTH = 16  # "lg_live_" + 8 characters, shown in the UI to identify a key

# Scope -> (description, workspace permission the key's creator must also hold)
SCOPES: dict[str, tuple[str, Permission | None]] = {
    "leads:read": ("Read leads and companies", None),
    "leads:write": ("Create and update leads", Permission.LEADS_WRITE),
    "campaigns:read": ("Read campaigns and enrollments", None),
    "campaigns:write": ("Enroll leads in campaigns", Permission.CAMPAIGNS_MANAGE),
    "replies:read": ("Read replies", None),
    "suppressions:read": ("Read the do-not-contact list", None),
    "suppressions:write": (
        "Add to and remove from the do-not-contact list",
        Permission.SETTINGS_MANAGE,
    ),
}


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_scopes(scopes: list[str], granted: frozenset[str]) -> list[str]:
    unknown = sorted(set(scopes) - SCOPES.keys())
    if unknown:
        raise ValidationFailedError(f"Unknown scopes: {', '.join(unknown)}")
    if not scopes:
        raise ValidationFailedError("Choose at least one scope")
    missing = sorted(s for s in scopes if (perm := SCOPES[s][1]) and perm not in granted)
    if missing:
        raise ValidationFailedError(f"Your role can't grant: {', '.join(missing)}")
    return sorted(set(scopes))


def create_api_key(
    db: Session,
    *,
    workspace_id: int,
    actor_id: int,
    name: str,
    scopes: list[str],
    expires_in_days: int | None,
) -> tuple[ApiKey, str]:
    raw = KEY_PREFIX + secrets.token_urlsafe(32)
    key = ApiKey(
        workspace_id=workspace_id,
        name=name.strip(),
        prefix=raw[:PREFIX_LENGTH],
        key_hash=hash_key(raw),
        scopes=scopes,
        created_by_id=actor_id,
        expires_at=datetime.now(UTC) + timedelta(days=expires_in_days) if expires_in_days else None,
    )
    db.add(key)
    db.flush()
    return key, raw


def find_key(db: Session, raw: str) -> ApiKey | None:
    """The live key matching ``raw``, looked up across workspaces by its prefix."""
    if not raw.startswith(KEY_PREFIX) or len(raw) < PREFIX_LENGTH + 16:
        return None
    with system_session(db):
        key = db.scalar(select(ApiKey).where(ApiKey.prefix == raw[:PREFIX_LENGTH]))
    if key is None or not hmac.compare_digest(key.key_hash, hash_key(raw)):
        return None
    if key.revoked_at is not None:
        return None
    expires = key.expires_at
    if expires is not None:
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires <= datetime.now(UTC):
            return None
    return key
