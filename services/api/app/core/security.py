import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import settings

_KEY_HELP = (
    "Generate one with: "
    'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


ACCESS_TOKEN_TYPE = "access"  # noqa: S105 - JWT "typ" claim, not a secret


def create_access_token(
    subject: str | int,
    *,
    token_version: int = 0,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes))
    payload: dict[str, Any] = {
        "sub": str(subject),
        "ver": token_version,
        "typ": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": expire,
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "exp", "typ"]},
    )
    if payload.get("typ") != ACCESS_TOKEN_TYPE:
        raise jwt.InvalidTokenError("Not an access token")
    return payload


def read_access_token(token: str) -> tuple[int, int] | None:
    """Return ``(user_id, token_version)`` for a valid access token, else None."""
    try:
        payload = decode_access_token(token)
        return int(payload["sub"]), int(payload.get("ver", 0))
    except (jwt.PyJWTError, ValueError, KeyError):
        return None


def _fernet() -> MultiFernet:
    keys = settings.encryption_keys()
    if not keys:
        raise RuntimeError(f"SECRET_ENCRYPTION_KEY is not set. {_KEY_HELP}")
    try:
        return MultiFernet([Fernet(key.encode()) for key in keys])
    except (ValueError, TypeError) as exc:
        raise RuntimeError("SECRET_ENCRYPTION_KEY is invalid for Fernet encryption") from exc


def ensure_encryption_key_configured() -> None:
    _fernet()


def encrypt_secret_payload(payload: str) -> str:
    """Encrypt with the newest key (the first in SECRET_ENCRYPTION_KEYS)."""
    return _fernet().encrypt(payload.encode("utf-8")).decode("utf-8")


def decrypt_secret_payload(encrypted_payload: str) -> str:
    """Decrypt with any configured key, so old ciphertexts survive a key rotation."""
    try:
        return _fernet().decrypt(encrypted_payload.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Stored secret could not be decrypted with the configured keys") from exc


def mask_secret_value(value: str | None) -> str:
    if not value:
        return ""
    trimmed = value.strip()
    if len(trimmed) <= 4:
        return "••••"
    return f"{'•' * 8}{trimmed[-4:]}"
