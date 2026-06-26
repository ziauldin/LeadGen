from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(subject: str | int, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(UTC) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])


def get_token_subject(token: str) -> str | None:
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        return str(subject) if subject is not None else None
    except JWTError:
        return None


def ensure_encryption_key_configured() -> None:
    if not settings.secret_encryption_key:
        raise RuntimeError(
            "SECRET_ENCRYPTION_KEY is not set. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"',
        )
    try:
        Fernet(settings.secret_encryption_key.encode())
    except Exception as exc:
        raise RuntimeError("SECRET_ENCRYPTION_KEY is invalid for Fernet encryption") from exc


def encrypt_secret_payload(payload: str) -> str:
    ensure_encryption_key_configured()
    return Fernet(settings.secret_encryption_key.encode()).encrypt(payload.encode("utf-8")).decode("utf-8")


def decrypt_secret_payload(encrypted_payload: str) -> str:
    ensure_encryption_key_configured()
    return (
        Fernet(settings.secret_encryption_key.encode())
        .decrypt(encrypted_payload.encode("utf-8"))
        .decode("utf-8")
    )


def mask_secret_value(value: str | None) -> str:
    if not value:
        return ""
    trimmed = value.strip()
    if len(trimmed) <= 4:
        return "••••"
    return f"{'•' * 8}{trimmed[-4:]}"
