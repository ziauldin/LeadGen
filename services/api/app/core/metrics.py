"""Prometheus metrics.

Request metrics are recorded per process (set PROMETHEUS_MULTIPROC_DIR to aggregate across
uvicorn workers). Business numbers (queue depth, worker heartbeat age) are read from the
database and Redis when /metrics is scraped, so they're correct however many processes run.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from datetime import UTC, datetime

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

HTTP_LATENCY = Histogram(
    "leadsgen_http_request_duration_seconds",
    "HTTP request latency by route template",
    ["method", "route", "status"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
EMAILS_SENT = Counter(
    "leadsgen_emails_sent_total", "Outreach emails accepted by a provider", ["provider"]
)
EMAIL_SEND_FAILURES = Counter(
    "leadsgen_email_send_failures_total", "Provider send failures", ["provider", "kind"]
)
DELIVERY_EVENTS = Counter(
    "leadsgen_delivery_events_total", "Delivery events processed (bounces, complaints...)", ["kind"]
)
REPLIES_RECEIVED = Counter(
    "leadsgen_replies_received_total", "Inbound replies stored", ["classification"]
)
LLM_TOKENS = Counter(
    "leadsgen_llm_tokens_total", "LLM tokens used", ["purpose", "key_source", "direction"]
)
WEBHOOKS_RECEIVED = Counter(
    "leadsgen_webhooks_received_total", "Provider webhooks accepted", ["provider"]
)


class BusinessCollector(Collector):
    """Queue depth and worker freshness, computed at scrape time."""

    def collect(self) -> Iterator[GaugeMetricFamily]:
        from sqlalchemy import func, select

        from app.core.database import SessionLocal
        from app.core.tenancy import system_session
        from app.models.email_message import EmailMessage
        from app.models.inbound import WebhookEvent

        messages = GaugeMetricFamily(
            "leadsgen_email_messages", "Email messages by status", labels=["status"]
        )
        webhooks = GaugeMetricFamily(
            "leadsgen_webhook_events_pending", "Stored provider webhooks not yet processed"
        )
        heartbeat = GaugeMetricFamily(
            "leadsgen_worker_heartbeat_age_seconds", "Seconds since a worker last ran the heartbeat"
        )
        try:
            db = SessionLocal()
            try:
                with system_session(db):
                    for status, count in db.execute(
                        select(EmailMessage.status, func.count(EmailMessage.id)).group_by(
                            EmailMessage.status
                        ),
                    ).all():
                        messages.add_metric([str(status)], count)
                    webhooks.add_metric(
                        [],
                        db.scalar(
                            select(func.count(WebhookEvent.id)).where(
                                WebhookEvent.status.in_(["pending", "failed"])
                            )
                        )
                        or 0,
                    )
            finally:
                db.close()
        except Exception:  # metrics must never break the scrape
            logger.exception("Could not collect database metrics")
        try:
            from app.services.health.checks import HEARTBEAT_KEY, _redis

            raw = _redis().get(HEARTBEAT_KEY)
            if raw:
                value = raw.decode() if isinstance(raw, bytes) else str(raw)
                age = (datetime.now(UTC) - datetime.fromisoformat(value)).total_seconds()
                heartbeat.add_metric([], age)
        except Exception:
            logger.debug("Worker heartbeat unavailable for metrics")
        yield messages
        yield webhooks
        yield heartbeat


def render_metrics() -> tuple[bytes, str]:
    registry = CollectorRegistry()
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_client import multiprocess

        multiprocess.MultiProcessCollector(registry)
    else:
        from prometheus_client import REGISTRY

        for collector in list(REGISTRY._collector_to_names):
            registry.register(collector)
    registry.register(BusinessCollector())
    return generate_latest(registry), CONTENT_TYPE_LATEST


class MetricsMiddleware:
    """Times every request and labels it with the matched route template, not the raw path."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") == "/metrics":
            await self.app(scope, receive, send)
            return
        start = time.perf_counter()
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            route = scope.get("route")
            template = getattr(route, "path", None) or "unmatched"
            HTTP_LATENCY.labels(scope.get("method", "GET"), template, str(status)).observe(
                time.perf_counter() - start
            )
