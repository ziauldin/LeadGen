import base64
import hashlib
import hmac
import json
import time

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import func, select

from app.models.inbound import WebhookEvent
from app.services.inbound.signatures import (
    SignatureError,
    verify_mailgun,
    verify_sendgrid,
    verify_svix,
)
from tests.conftest import TestingSessionLocal, auth_headers, get_client

SVIX_SECRET = "whsec_" + base64.b64encode(b"super-secret-signing-key-123456").decode()


def svix_headers(body: bytes, msg_id: str = "msg_1", ts: int | None = None) -> dict[str, str]:
    ts = ts or int(time.time())
    key = base64.b64decode(SVIX_SECRET.removeprefix("whsec_"))
    sig = base64.b64encode(
        hmac.new(key, f"{msg_id}.{ts}.".encode() + body, hashlib.sha256).digest(),
    ).decode()
    return {"svix-id": msg_id, "svix-timestamp": str(ts), "svix-signature": f"v1,{sig}"}


# --- unit -------------------------------------------------------------------------------------


def test_svix_valid_invalid_and_stale():
    body = b'{"type":"email.delivered"}'
    headers = svix_headers(body)
    verify_svix(
        SVIX_SECRET,
        msg_id=headers["svix-id"],
        timestamp=headers["svix-timestamp"],
        signature_header=headers["svix-signature"],
        body=body,
    )
    with pytest.raises(SignatureError):
        verify_svix(
            SVIX_SECRET,
            msg_id=headers["svix-id"],
            timestamp=headers["svix-timestamp"],
            signature_header=headers["svix-signature"],
            body=body + b" ",
        )
    old = svix_headers(body, ts=int(time.time()) - 3600)
    with pytest.raises(SignatureError):
        verify_svix(
            SVIX_SECRET,
            msg_id=old["svix-id"],
            timestamp=old["svix-timestamp"],
            signature_header=old["svix-signature"],
            body=body,
        )


def test_sendgrid_ecdsa():
    private = ec.generate_private_key(ec.SECP256R1())
    public_b64 = base64.b64encode(
        private.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
    ).decode()
    body = b'[{"event":"delivered"}]'
    ts = str(int(time.time()))
    signature = base64.b64encode(
        private.sign(ts.encode() + body, ec.ECDSA(hashes.SHA256())),
    ).decode()
    verify_sendgrid(public_b64, signature=signature, timestamp=ts, body=body)
    with pytest.raises(SignatureError):
        verify_sendgrid(public_b64, signature=signature, timestamp=ts, body=b"[]")


def test_mailgun_hmac():
    ts = str(int(time.time()))
    token = "abc123token"
    sig = hmac.new(b"mg-key", f"{ts}{token}".encode(), hashlib.sha256).hexdigest()
    verify_mailgun("mg-key", timestamp=ts, token=token, signature=sig)
    with pytest.raises(SignatureError):
        verify_mailgun("other-key", timestamp=ts, token=token, signature=sig)


# --- endpoint ---------------------------------------------------------------------------------


def _resend_credential(client, headers) -> str:
    response = client.post(
        "/provider-settings",
        headers=headers,
        json={
            "provider_type": "email",
            "provider_name": "resend",
            "config": {
                "api_key": "re_test_123456",
                "from_email": "sam@acme.example",
                "webhook_secret": SVIX_SECRET,
            },
        },
    )
    assert response.status_code == 200, response.text
    url = response.json()["webhook_urls"]["events_and_inbound"]
    return url.split("/webhooks/")[1]


def _event_count() -> int:
    db = TestingSessionLocal()
    try:
        return db.scalar(select(func.count(WebhookEvent.id))) or 0
    finally:
        db.close()


def test_webhook_endpoint_accepts_signed_and_rejects_bad_requests():
    client = get_client()
    headers = auth_headers(client)
    path = _resend_credential(client, headers)
    body = json.dumps(
        {"type": "email.delivered", "data": {"email_id": "x", "to": ["a@b.co"]}}
    ).encode()

    ok = client.post(f"/webhooks/{path}", content=body, headers=svix_headers(body, "msg_ok"))
    assert ok.status_code == 200
    assert ok.json() == {"received": 1, "stored": 1}

    bad = svix_headers(body, "msg_bad")
    bad["svix-signature"] = "v1,AAAA"
    assert client.post(f"/webhooks/{path}", content=body, headers=bad).status_code == 401

    stale = svix_headers(body, "msg_stale", ts=int(time.time()) - 3600)
    assert client.post(f"/webhooks/{path}", content=body, headers=stale).status_code == 401

    # Replaying the same event id is accepted but stored once.
    replay = client.post(f"/webhooks/{path}", content=body, headers=svix_headers(body, "msg_ok"))
    assert replay.json() == {"received": 1, "stored": 0}
    assert _event_count() == 1


def test_unknown_token_and_wrong_provider_are_404():
    client = get_client()
    headers = auth_headers(client)
    path = _resend_credential(client, headers)
    token = path.split("/")[-1]
    body = b"{}"
    assert client.post("/webhooks/resend/not-a-token", content=body).status_code == 404
    assert client.post(f"/webhooks/mailgun/{token}/events", content=body).status_code == 404
