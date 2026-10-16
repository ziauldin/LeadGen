"""OpenTelemetry tracing, enabled when OTEL_EXPORTER_OTLP_ENDPOINT is set.

Traces FastAPI requests, Celery tasks, SQLAlchemy queries and outgoing httpx calls, and
exports them over OTLP/HTTP to any compatible backend (Grafana Tempo, Honeycomb, Datadog...).
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)
_initialised = False


def init_tracing(component: str, *, app: Any = None) -> bool:
    global _initialised
    if not settings.otel_exporter_otlp_endpoint:
        return False
    if not _initialised:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

        from app.core.database import engine

        provider = TracerProvider(
            resource=Resource.create(
                {
                    "service.name": f"leadsgen-{component}",
                    "service.version": settings.railway_git_commit_sha or "dev",
                    "deployment.environment": settings.environment,
                },
            ),
            sampler=ParentBasedTraceIdRatio(settings.otel_sample_ratio),
        )
        endpoint = settings.otel_exporter_otlp_endpoint.rstrip("/")
        if not endpoint.endswith("/v1/traces"):
            endpoint += "/v1/traces"
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        SQLAlchemyInstrumentor().instrument(engine=engine)
        HTTPXClientInstrumentor().instrument()
        if component == "worker":
            from opentelemetry.instrumentation.celery import CeleryInstrumentor

            CeleryInstrumentor().instrument()
        _initialised = True
        logger.info("Tracing enabled for %s", component)
    if app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, excluded_urls="health,health/ready,metrics")
    return True
