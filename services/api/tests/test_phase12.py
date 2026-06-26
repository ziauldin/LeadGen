from unittest.mock import patch

from tests.conftest import auth_headers, get_client

from tests.test_phase7 import WELLPREDICT_STEP


def test_health_liveness():
    client = get_client()
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "environment" in body


def test_health_ready_when_dependencies_ok(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.health.check_redis",
        lambda: (True, None),
    )
    client = get_client()
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert {d["name"]: d["status"] for d in body["dependencies"]} == {
        "database": "ok",
        "redis": "ok",
    }


def test_health_ready_returns_503_when_redis_down(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.health.check_redis",
        lambda: (False, "connection refused"),
    )
    client = get_client()
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_celery_beat_schedule_configured():
    from app.core.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule
    assert "process-campaign-sends" in schedule
    assert schedule["process-campaign-sends"]["task"] == "campaign.process_sends"
    assert "sync-replies" in schedule
    assert schedule["sync-replies"]["task"] == "replies.sync"


def test_google_cse_provider_requires_credentials():
    from app.services.search.external_providers import GoogleCseSearchProvider, ProviderConfigurationError

    provider = GoogleCseSearchProvider(api_key="", search_engine_id="")
    try:
        provider.search("quality manager UK", limit=5)
        raise AssertionError("expected ProviderConfigurationError")
    except ProviderConfigurationError as exc:
        assert "api_key" in str(exc)


def test_search_factory_supports_external_providers():
    from app.services.search.provider_factory import get_search_provider_for_user

    client = get_client()
    headers = auth_headers(client)
    credential_id = client.post(
        "/provider-settings",
        headers=headers,
        json={
            "provider_type": "search",
            "provider_name": "bing",
            "config": {"api_key": "test-bing-key"},
        },
    ).json()["id"]
    client.patch(f"/provider-settings/{credential_id}/activate", headers=headers)

    from tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    try:
        user_id = client.get("/auth/me", headers=headers).json()["id"]
        provider = get_search_provider_for_user(db, user_id)
        assert provider.provider_name == "bing"
    finally:
        db.close()


def test_mvp_workflow_smoke():
    """End-to-end API smoke: niche → search → lead → score → email → campaign → reply → dashboard."""
    client = get_client()
    headers = auth_headers(client)

    niche_id = client.post(
        "/niches",
        headers=headers,
        json={
            "name": "Smoke Niche",
            "country": "UK",
            "industry": "Food Manufacturing",
            "target_roles": ["Quality Manager"],
            "keywords": ["governance"],
            "exclusion_keywords": [],
        },
    ).json()["id"]

    queries = client.post(
        "/searches/generate-queries",
        headers=headers,
        json={"niche_id": niche_id},
    ).json()["queries"]
    assert queries

    search = client.post(
        "/searches/run",
        headers=headers,
        json={"niche_id": niche_id, "query": queries[0], "limit": 3},
    )
    assert search.status_code == 201
    search_id = search.json()["id"]
    first_url = search.json()["results"][0]["url"]

    saved = client.post(
        f"/searches/{search_id}/save-results",
        headers=headers,
        json={"selected_urls": [first_url]},
    )
    assert saved.status_code == 200
    assert saved.json()["created"] == 1

    client.post(
        "/settings",
        headers=headers,
        json={"sender_name": "Sam Founder", "sender_company": "WellPredict"},
    )

    client.post(
        "/leads/import-csv",
        headers=headers,
        files={
            "file": (
                "leads.csv",
                "full_name,job_title,company,website,linkedin_url,email,source_url,"
                "compliance_source_note,niche\n"
                "Alex Morgan,Quality Manager,Example Foods,https://example-foods.co.uk,,"
                "alex@example-foods.co.uk,https://example.com/listing,"
                "Found via public listing,Smoke Niche\n",
                "text/csv",
            ),
        },
    )

    leads = client.get(f"/leads?niche_id={niche_id}", headers=headers).json()["items"]
    lead_id = next(item["id"] for item in leads if item.get("primary_email"))

    recalc = client.post("/scoring/recalculate", headers=headers, json={"niche_id": niche_id})
    assert recalc.status_code == 200
    assert recalc.json()["updated"] >= 1

    readiness = client.get(f"/leads/{lead_id}/outreach-readiness", headers=headers).json()
    assert readiness["ready"] is True

    preview = client.post(
        "/emails/preview",
        headers=headers,
        json={
            "lead_id": lead_id,
            "subject_template": WELLPREDICT_STEP["subject_template"],
            "body_template": WELLPREDICT_STEP["body_template"],
        },
    )
    assert preview.status_code == 200

    campaign_id = client.post(
        "/campaigns",
        headers=headers,
        json={
            "niche_id": niche_id,
            "name": "Smoke campaign",
            "daily_send_limit": 10,
            "sending_window_start": "00:00",
            "sending_window_end": "23:59",
            "steps": [WELLPREDICT_STEP],
        },
    ).json()["id"]

    message_id = client.post(
        f"/campaigns/{campaign_id}/add-leads",
        headers=headers,
        json={"lead_ids": [lead_id]},
    ).json()["message_ids"][0]

    client.post("/emails/approve", headers=headers, json={"email_message_id": message_id})
    client.post(f"/campaigns/{campaign_id}/start", headers=headers)
    sent = client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers)
    assert sent.json()["sent"] == 1

    lead = client.get(f"/leads/{lead_id}", headers=headers).json()
    assert lead["status"] == "contacted"

    client.post("/replies/sync", headers=headers)
    replies = client.get("/replies", headers=headers).json()["items"]
    assert len(replies) >= 1

    summary = client.get("/dashboard/summary", headers=headers).json()
    assert summary["total_leads"] >= 2
    assert summary["active_campaigns"] >= 1
    assert "lead_status_counts" in summary

    assert client.get("/health").status_code == 200
