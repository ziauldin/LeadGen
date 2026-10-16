from app.core import metrics
from app.core.config import settings
from app.core.tracing import init_tracing
from tests.conftest import auth_headers, get_client


def test_metrics_endpoint_is_off_without_a_token(monkeypatch):
    monkeypatch.setattr(settings, "metrics_token", "")
    assert get_client().get("/metrics").status_code == 404


def test_metrics_requires_the_bearer_token(monkeypatch):
    monkeypatch.setattr(settings, "metrics_token", "scrape-secret")
    client = get_client()
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer nope"}).status_code == 401

    auth_headers(client)  # some traffic, so request metrics exist
    response = client.get("/metrics", headers={"Authorization": "Bearer scrape-secret"})
    assert response.status_code == 200
    body = response.text
    assert "leadsgen_http_request_duration_seconds_bucket" in body
    assert 'route="/auth/login"' in body
    assert "leadsgen_webhook_events_pending" in body


def test_business_counters_are_registered():
    metrics.EMAILS_SENT.labels("mock").inc()
    body, content_type = metrics.render_metrics()
    assert b'leadsgen_emails_sent_total{provider="mock"}' in body
    assert content_type.startswith("text/plain")


def test_tracing_is_off_without_an_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "otel_exporter_otlp_endpoint", "")
    assert init_tracing("api") is False
