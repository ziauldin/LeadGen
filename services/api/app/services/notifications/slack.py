"""Slack incoming webhooks: one per workspace, stored encrypted."""

from __future__ import annotations

import json
from urllib.parse import urlparse

import httpx

from app.core.errors import ValidationFailedError
from app.core.http import FetchError, UnsafeURLError, safe_post_bytes
from app.core.security import decrypt_secret_payload, encrypt_secret_payload
from app.models.workspace import WorkspaceSettings


def validate_webhook_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if (
        parsed.scheme != "https"
        or parsed.hostname != "hooks.slack.com"
        or not parsed.path.startswith("/services/")
    ):
        raise ValidationFailedError(
            "Paste a Slack incoming webhook URL (https://hooks.slack.com/services/...)"
        )
    return url.strip()


def set_webhook(ws_settings: WorkspaceSettings, url: str | None) -> None:
    ws_settings.slack_webhook_encrypted = (
        encrypt_secret_payload(validate_webhook_url(url)) if url else None
    )


def send(ws_settings: WorkspaceSettings, text: str) -> tuple[bool, str | None]:
    if not ws_settings.slack_webhook_encrypted:
        return False, "Slack isn't connected"
    url = decrypt_secret_payload(ws_settings.slack_webhook_encrypted)
    body = json.dumps({"text": text}).encode()
    try:
        with httpx.Client(headers={"Content-Type": "application/json"}) as client:
            result = safe_post_bytes(client, url, body, timeout=10.0, max_bytes=10_000)
    except (FetchError, UnsafeURLError) as exc:
        return False, str(exc)
    if 200 <= result.status_code < 300:
        return True, None
    return False, f"Slack answered {result.status_code}: {result.text[:200]}"
