"""Account lifecycle: registration, login with lockout, email verification, password reset."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AuthenticationError, ConflictError
from app.core.security import get_password_hash, verify_password
from app.models.audit_log import AuditLog
from app.models.enums import UserRole
from app.models.user import User
from app.services.auth import tokens
from app.services.platform_email.dispatch import send_platform_email
from app.services.platform_email.templates import password_reset_email, verification_email

logger = logging.getLogger(__name__)

MAX_FAILED_LOGINS = 5
BASE_LOCKOUT = timedelta(minutes=15)
MAX_LOCKOUT = timedelta(hours=24)
GENERIC_LOGIN_ERROR = "Incorrect email or password"


def _now() -> datetime:
    return datetime.now(UTC)


def _audit(db: Session, user_id: int | None, action: str, metadata: dict | None = None) -> None:
    db.add(
        AuditLog(
            actor_id=user_id,
            action=action,
            entity_type="user",
            entity_id=user_id,
            metadata_=metadata,
        ),
    )


def register_user(db: Session, *, name: str, email: str, password: str) -> User:
    normalized = email.strip().lower()
    if db.scalar(select(User.id).where(User.email == normalized)) is not None:
        raise ConflictError("A user with this email already exists")

    user = User(
        name=name.strip(),
        email=normalized,
        hashed_password=get_password_hash(password),
        role=UserRole.OPERATOR,
    )
    db.add(user)
    db.flush()
    _audit(db, user.id, "user_registered")
    db.commit()
    db.refresh(user)
    send_verification(db, user)
    return user


def _lockout_duration(failed_count: int) -> timedelta:
    # 5 failures -> 15 min, 10 -> 30 min, 15 -> 60 min ... capped at 24 h.
    multiplier = 2 ** max(0, failed_count // MAX_FAILED_LOGINS - 1)
    return min(BASE_LOCKOUT * multiplier, MAX_LOCKOUT)


def authenticate(db: Session, *, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        # Spend comparable time to avoid revealing which emails exist.
        verify_password(password, get_password_hash("timing-equaliser"))
        raise AuthenticationError(GENERIC_LOGIN_ERROR)

    now = _now()
    locked_until = user.locked_until
    if locked_until is not None:
        locked_until = locked_until if locked_until.tzinfo else locked_until.replace(tzinfo=UTC)
        if locked_until > now:
            raise AuthenticationError(
                "Too many failed sign-in attempts. Try again later or reset your password.",
            )

    if not user.is_active or not verify_password(password, user.hashed_password):
        user.failed_login_count += 1
        if user.failed_login_count % MAX_FAILED_LOGINS == 0:
            user.locked_until = now + _lockout_duration(user.failed_login_count)
            _audit(db, user.id, "login_locked", {"failed_attempts": user.failed_login_count})
        db.commit()
        raise AuthenticationError(GENERIC_LOGIN_ERROR)

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    db.commit()
    return user


CAPTCHA_AFTER_FAILURES = 3


def needs_captcha(db: Session, email: str) -> bool:
    """After a few failed sign-ins for an address, a CAPTCHA is required (when configured)."""
    from app.services.auth.protection import captcha_enabled

    if not captcha_enabled():
        return False
    failed = db.scalar(select(User.failed_login_count).where(User.email == email.strip().lower()))
    return (failed or 0) >= CAPTCHA_AFTER_FAILURES


def change_password(db: Session, user: User, *, current: str, new: str) -> None:
    if not verify_password(current, user.hashed_password):
        raise AuthenticationError("Your current password is incorrect")
    user.hashed_password = get_password_hash(new)
    user.password_changed_at = _now()
    user.token_version += 1
    tokens.revoke_all_for_user(db, user.id)
    _audit(db, user.id, "password_changed")
    db.commit()


def send_verification(db: Session, user: User) -> None:
    if user.email_verified_at is not None:
        return
    raw = tokens.create_email_action_token(db, user, tokens.PURPOSE_VERIFY)
    db.commit()
    send_platform_email(verification_email(user.email, user.name, raw))


def verify_email(db: Session, raw_token: str) -> User:
    user = tokens.consume_email_action_token(db, raw_token, tokens.PURPOSE_VERIFY)
    first_time = user.email_verified_at is None
    if first_time:
        user.email_verified_at = _now()
        _audit(db, user.id, "email_verified")
    db.commit()
    if first_time:
        from app.services.notifications.lifecycle import send_welcome

        send_welcome(db, user)
    return user


def request_password_reset(db: Session, email: str) -> None:
    """Always succeeds from the caller's point of view (no account enumeration)."""
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not user.is_active:
        return
    raw = tokens.create_email_action_token(db, user, tokens.PURPOSE_RESET)
    _audit(db, user.id, "password_reset_requested")
    db.commit()
    send_platform_email(password_reset_email(user.email, user.name, raw))


def reset_password(db: Session, raw_token: str, new_password: str) -> User:
    user = tokens.consume_email_action_token(db, raw_token, tokens.PURPOSE_RESET)
    user.hashed_password = get_password_hash(new_password)
    user.password_changed_at = _now()
    user.token_version += 1  # invalidates every outstanding access token
    user.failed_login_count = 0
    user.locked_until = None
    if user.email_verified_at is None:
        # Receiving the reset email proves ownership of the address.
        user.email_verified_at = _now()
    tokens.revoke_all_for_user(db, user.id)
    _audit(db, user.id, "password_reset")
    db.commit()
    return user


def logout_everywhere(db: Session, user: User) -> None:
    user.token_version += 1
    tokens.revoke_all_for_user(db, user.id)
    _audit(db, user.id, "logout_all")
    db.commit()
