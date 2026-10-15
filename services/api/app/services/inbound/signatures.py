"""Webhook signature verification for each provider."""

from __future__ import annotations

import base64
import hashlib
import hmac
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_der_public_key, load_pem_public_key

TOLERANCE_SECONDS = 5 * 60


class SignatureError(Exception):
    """The webhook could not be authenticated."""


def _fresh(timestamp: str, tolerance: int = TOLERANCE_SECONDS, now: float | None = None) -> None:
    try:
        sent = int(float(timestamp))
    except (TypeError, ValueError) as exc:
        raise SignatureError("Invalid timestamp") from exc
    if abs((now or time.time()) - sent) > tolerance:
        raise SignatureError("Timestamp outside the allowed window")


def verify_svix(
    secret: str,
    *,
    msg_id: str | None,
    timestamp: str | None,
    signature_header: str | None,
    body: bytes,
    now: float | None = None,
) -> None:
    """Resend (Svix): HMAC-SHA256 over ``{id}.{timestamp}.{body}`` with the ``whsec_`` secret."""
    if not (secret and msg_id and timestamp and signature_header):
        raise SignatureError("Missing Svix headers or secret")
    _fresh(timestamp, now=now)
    key = base64.b64decode(secret.removeprefix("whsec_"))
    signed = f"{msg_id}.{timestamp}.".encode() + body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    for item in signature_header.split():
        version, _, value = item.partition(",")
        if version == "v1" and hmac.compare_digest(value, expected):
            return
    raise SignatureError("Signature mismatch")


def _load_public_key(public_key: str) -> ec.EllipticCurvePublicKey:
    text = public_key.strip()
    if text.startswith("-----BEGIN"):
        key = load_pem_public_key(text.encode())
    else:
        key = load_der_public_key(base64.b64decode(text))
    if not isinstance(key, ec.EllipticCurvePublicKey):
        raise SignatureError("Verification key is not an EC public key")
    return key


def verify_sendgrid(
    public_key: str,
    *,
    signature: str | None,
    timestamp: str | None,
    body: bytes,
    now: float | None = None,
) -> None:
    """SendGrid Event Webhook: ECDSA P-256/SHA-256 over ``timestamp + body``."""
    if not (public_key and signature and timestamp):
        raise SignatureError("Missing SendGrid signature headers or key")
    _fresh(timestamp, now=now)
    try:
        _load_public_key(public_key).verify(
            base64.b64decode(signature),
            timestamp.encode() + body,
            ec.ECDSA(hashes.SHA256()),
        )
    except (InvalidSignature, ValueError) as exc:
        raise SignatureError("Signature mismatch") from exc


def verify_mailgun(
    signing_key: str,
    *,
    timestamp: str | None,
    token: str | None,
    signature: str | None,
    now: float | None = None,
) -> None:
    """Mailgun: HMAC-SHA256(signing_key, timestamp + token), hex encoded."""
    if not (signing_key and timestamp and token and signature):
        raise SignatureError("Missing Mailgun signature fields or key")
    _fresh(timestamp, tolerance=15 * 60, now=now)
    expected = hmac.new(
        signing_key.encode(),
        f"{timestamp}{token}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise SignatureError("Signature mismatch")
