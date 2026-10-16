"""Sentry setup shared by the API, Celery worker and beat."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_SENSITIVE_KEYS = {
    "password",
    "body",
    "subject",
    "recipient_email",
    "email",
    "authorization",
    "cookie",
    "api_key",
    "access_token",
    "refresh_token",
    "token",
}


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[redacted]" if str(key).lower() in _SENSITIVE_KEYS else _scrub(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def _before_send(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("data", None)
        request.pop("cookies", None)
        if isinstance(request.get("headers"), dict):
            request["headers"] = _scrub(request["headers"])
    if "extra" in event:
        event["extra"] = _scrub(event["extra"])
    return event


def init_sentry(component: str) -> bool:
    """Initialise Sentry when SENTRY_DSN is set. Returns True when enabled."""
    if not settings.sentry_dsn:
        return False

    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=settings.railway_git_commit_sha or None,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
        before_send=_before_send,  # type: ignore[arg-type]
        integrations=[FastApiIntegration(), CeleryIntegration(), SqlalchemyIntegration()],
    )
    sentry_sdk.set_tag("component", component)
    logger.info("Sentry enabled for %s", component)
    return True
