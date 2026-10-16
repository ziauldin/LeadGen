"""Two-factor authentication with authenticator apps (TOTP, RFC 6238) and recovery codes.

The TOTP secret is encrypted at rest. Recovery codes are shown once and stored as hashes;
each works a single time.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
import pyotp
import segno
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AuthenticationError, ValidationFailedError
from app.core.security import decrypt_secret_payload, encrypt_secret_payload, verify_password
from app.models.audit_log import AuditLog
from app.models.user import User

ISSUER = "LeadsGen"
RECOVERY_CODE_COUNT = 10
MFA_TOKEN_TYPE = "mfa"  # noqa: S105 - token type label, not a secret
MFA_TOKEN_MINUTES = 5


def _audit(db: Session, user: User, action: str) -> None:
    db.add(AuditLog(actor_id=user.id, action=action, entity_type="user", entity_id=user.id))


def _hash_code(code: str) -> str:
    normalized = code.replace("-", "").replace(" ", "").lower()
    return hashlib.sha256(f"{settings.secret_key}:{normalized}".encode()).hexdigest()


def _totp(secret: str) -> pyotp.TOTP:
    return pyotp.TOTP(secret)


def is_enabled(user: User) -> bool:
    return user.totp_enabled_at is not None and bool(user.totp_secret_encrypted)


def begin_setup(db: Session, user: User) -> dict[str, str]:
    """Create a new (not yet active) secret and return what the app needs to show a QR code."""
    if is_enabled(user):
        raise ValidationFailedError("Two-factor authentication is already on")
    secret = pyotp.random_base32()
    user.totp_secret_encrypted = encrypt_secret_payload(secret)
    db.commit()
    uri = _totp(secret).provisioning_uri(name=user.email, issuer_name=ISSUER)
    svg = segno.make(uri, error="m").svg_inline(scale=4, border=2)
    qr = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
    return {"secret": secret, "otpauth_uri": uri, "qr_code": qr}


def _verify_totp(user: User, code: str) -> bool:
    """Accept the current, previous or next 30-second code, each time step only once.

    Remembering the last accepted step stops a code seen over someone's shoulder (or in a
    phishing proxy) from being replayed within its validity window.
    """
    if not user.totp_secret_encrypted:
        return False
    digits = code.replace(" ", "")
    if not (digits.isdigit() and len(digits) == 6):
        return False
    totp = _totp(decrypt_secret_payload(user.totp_secret_encrypted))
    now = datetime.now(UTC)
    current_step = totp.timecode(now)
    for offset in (-1, 0, 1):
        step = current_step + offset
        if hmac.compare_digest(totp.generate_otp(step), digits):
            if user.totp_last_step is not None and step <= user.totp_last_step:
                return False
            user.totp_last_step = step
            return True
    return False


def _new_recovery_codes(user: User) -> list[str]:
    codes = [
        f"{secrets.token_hex(2)}-{secrets.token_hex(2)}-{secrets.token_hex(2)}"
        for _ in range(RECOVERY_CODE_COUNT)
    ]
    user.recovery_code_hashes = [_hash_code(code) for code in codes]
    return codes


def enable(db: Session, user: User, code: str) -> list[str]:
    """Confirm the authenticator works and turn 2FA on. Returns the recovery codes (once)."""
    if is_enabled(user):
        raise ValidationFailedError("Two-factor authentication is already on")
    if not _verify_totp(user, code):
        raise ValidationFailedError("That code didn't match. Check your authenticator app's time.")
    user.totp_enabled_at = datetime.now(UTC)
    codes = _new_recovery_codes(user)
    _audit(db, user, "mfa_enabled")
    db.commit()
    return codes


def disable(db: Session, user: User, *, password: str, code: str) -> None:
    if not is_enabled(user):
        return
    if not verify_password(password, user.hashed_password) or not verify_code(db, user, code):
        raise AuthenticationError("Password or code is incorrect")
    user.totp_secret_encrypted = None
    user.totp_last_step = None
    user.totp_enabled_at = None
    user.recovery_code_hashes = None
    _audit(db, user, "mfa_disabled")
    db.commit()


def regenerate_recovery_codes(db: Session, user: User, code: str) -> list[str]:
    if not is_enabled(user) or not _verify_totp(user, code):
        raise ValidationFailedError("Enter a current code from your authenticator app")
    codes = _new_recovery_codes(user)
    _audit(db, user, "mfa_recovery_codes_regenerated")
    db.commit()
    return codes


def verify_code(db: Session, user: User, code: str) -> bool:
    """Accept a TOTP code or an unused recovery code (which is then used up)."""
    if _verify_totp(user, code):
        return True
    hashed = _hash_code(code)
    remaining = list(user.recovery_code_hashes or [])
    for stored in remaining:
        if hmac.compare_digest(stored, hashed):
            remaining.remove(stored)
            user.recovery_code_hashes = remaining
            _audit(db, user, "mfa_recovery_code_used")
            return True
    return False


def recovery_codes_left(user: User) -> int:
    return len(user.recovery_code_hashes or [])


def issue_mfa_token(user: User) -> str:
    """A short-lived token proving the password step passed, exchanged for a session with a code."""
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user.id),
            "typ": MFA_TOKEN_TYPE,
            "ver": user.token_version,
            "iat": now,
            "exp": now + timedelta(minutes=MFA_TOKEN_MINUTES),
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def read_mfa_token(db: Session, token: str) -> User:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Your sign-in expired. Start again.") from exc
    if payload.get("typ") != MFA_TOKEN_TYPE:
        raise AuthenticationError("Your sign-in expired. Start again.")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active or payload.get("ver") != user.token_version:
        raise AuthenticationError("Your sign-in expired. Start again.")
    return user
