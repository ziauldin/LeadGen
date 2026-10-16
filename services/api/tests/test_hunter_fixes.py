from unittest.mock import patch

from app.services.enrichment.email_discovery.base import DiscoveredEmail
from app.services.enrichment.website_crawler import CrawledPage
from tests.conftest import auth_headers, get_client

CSV = (
    "full_name,job_title,company,website,linkedin_url,email,source_url,compliance_source_note,niche\n"
    "A B,CEO,Acme,https://acme-foods.co.uk,,,https://s.example,n,N\n"
)
DISCOVER = (
    "app.services.enrichment.email_discovery.hunter_provider."
    "HunterEmailDiscoveryProvider.discover_by_domain"
)


class AllowAll:
    allow_all = True


def _setup(client, headers):
    client.post(
        "/niches",
        headers=headers,
        json={
            "name": "N",
            "country": "UK",
            "industry": "Legal",
            "target_roles": [],
            "keywords": [],
        },
    )
    client.post("/leads/import-csv", headers=headers, files={"file": ("l.csv", CSV, "text/csv")})
    return client.get("/companies", headers=headers).json()["items"][0]["id"]


def _save_hunter(client, headers):
    return client.post(
        "/provider-settings",
        headers=headers,
        json={
            "provider_type": "email_discovery",
            "provider_name": "hunter",
            "config": {"api_key": "hunter-test-key-1234"},
        },
    )


def test_hunter_credentials_can_be_saved_and_activated():
    client = get_client()
    headers = auth_headers(client)
    response = _save_hunter(client, headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["display_name"] == "Hunter.io"
    assert "1234" in body["masked_summary"]
    activated = client.patch(f"/provider-settings/{body['id']}/activate", headers=headers)
    assert activated.status_code == 200


def test_hunter_rejected_for_wrong_provider_type():
    client = get_client()
    headers = auth_headers(client)
    response = client.post(
        "/provider-settings",
        headers=headers,
        json={"provider_type": "email", "provider_name": "hunter", "config": {"api_key": "k"}},
    )
    assert response.status_code == 400


def test_hunter_results_with_missing_fields_complete_enrichment():
    client = get_client()
    headers = auth_headers(client)
    company_id = _setup(client, headers)
    credential = _save_hunter(client, headers).json()
    client.patch(f"/provider-settings/{credential['id']}/activate", headers=headers)

    hunter_result = [
        DiscoveredEmail(
            email="jane.doe@acme-foods.co.uk",
            email_type="named",
            confidence=None,
            source="hunter",
            source_url="acme-foods.co.uk",
        ),
    ]
    page = CrawledPage(url="https://acme-foods.co.uk", html="<p>no emails</p>")
    with (
        patch(
            "app.services.enrichment.enricher.fetch_robots_parser",
            return_value=(AllowAll(), True),
        ),
        patch(
            "app.services.enrichment.enricher.crawl_company_site",
            return_value=([page], None),
        ),
        patch(DISCOVER, return_value=hunter_result),
    ):
        response = client.post(f"/companies/{company_id}/enrich?sync=true", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert "Hunter" in response.json()["message"]
    company = client.get(f"/companies/{company_id}", headers=headers).json()
    assert [c["email"] for c in company["email_contacts"]] == ["jane.doe@acme-foods.co.uk"]


def test_unexpected_crawler_failure_never_leaves_company_in_progress():
    client = get_client()
    headers = auth_headers(client)
    company_id = _setup(client, headers)

    with patch(
        "app.services.enrichment.enricher.fetch_robots_parser",
        side_effect=RuntimeError("boom"),
    ):
        response = client.post(f"/companies/{company_id}/enrich?sync=true", headers=headers)

    assert response.json()["status"] == "failed"
    assert "boom" not in response.json()["message"]


def _enrich(client, headers, company_id):
    page = CrawledPage(url="https://acme-foods.co.uk", html="<p>no emails</p>")
    with (
        patch(
            "app.services.enrichment.enricher.fetch_robots_parser",
            return_value=(AllowAll(), True),
        ),
        patch(
            "app.services.enrichment.enricher.crawl_company_site",
            return_value=([page], None),
        ),
        patch(DISCOVER, return_value=[]) as discover,
    ):
        response = client.post(f"/companies/{company_id}/enrich?sync=true", headers=headers)
        assert response.status_code == 200, response.text
    return discover


def _lookups(client, headers) -> int:
    usage = {u["metric"]: u for u in client.get("/billing", headers=headers).json()["usage"]}
    return usage["daily_hunter_lookups"]["used"]


def test_own_hunter_key_is_not_counted_against_the_plan():
    client = get_client()
    headers = auth_headers(client)
    company_id = _setup(client, headers)
    credential = _save_hunter(client, headers).json()
    client.patch(f"/provider-settings/{credential['id']}/activate", headers=headers)
    assert _enrich(client, headers, company_id).called
    assert _lookups(client, headers) == 0


def test_platform_hunter_key_is_counted(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "hunter_enabled", True)
    monkeypatch.setattr(settings, "email_discovery_provider", "hunter")
    monkeypatch.setattr(settings, "hunter_api_key", "platform-hunter-key")
    client = get_client()
    headers = auth_headers(client)
    company_id = _setup(client, headers)
    assert _enrich(client, headers, company_id).called
    assert _lookups(client, headers) == 1
