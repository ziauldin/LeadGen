from unittest.mock import patch

from app.services.enrichment.website_crawler import CrawledPage
from tests.conftest import auth_headers, get_client

SAMPLE_HTML = """
<html>
  <body>
    <a href="/contact">Contact</a>
    <a href="/about-us">About</a>
    <p>Reach us at quality@example-foods.co.uk or info@example-foods.co.uk</p>
  </body>
</html>
"""

CONTACT_HTML = """
<html><body><p>hello@example-foods.co.uk</p></body></html>
"""


def test_enrich_company_sync_extracts_emails():
    client = get_client()
    headers = auth_headers(client)

    niche_id = client.post(
        "/niches",
        headers=headers,
        json={
            "name": "Food Niche",
            "country": "UK",
            "industry": "Food Manufacturing",
            "target_roles": ["Quality Manager"],
            "keywords": ["governance"],
            "exclusion_keywords": [],
        },
    ).json()["id"]

    import_resp = client.post(
        "/leads/import-csv",
        headers=headers,
        files={
            "file": (
                "leads.csv",
                "full_name,job_title,company,website,linkedin_url,email,source_url,"
                "compliance_source_note,niche\n"
                "Alex Morgan,Quality Manager,Example Foods,https://example-foods.co.uk,,,"
                "https://example.com/source,Public listing,Food Niche\n",
                "text/csv",
            ),
        },
    )
    assert import_resp.status_code == 200

    companies = client.get("/companies", headers=headers).json()
    company_id = companies["items"][0]["id"]

    def fake_crawl(base_url: str):
        return [
            CrawledPage(url=base_url, html=SAMPLE_HTML),
            CrawledPage(url=f"{base_url.rstrip('/')}/contact", html=CONTACT_HTML),
        ], None

    class AllowAllParser:
        allow_all = True

    with (
        patch(
            "app.services.enrichment.enricher.crawl_company_site",
            side_effect=fake_crawl,
        ),
        patch(
            "app.services.enrichment.enricher.fetch_robots_parser",
            return_value=(AllowAllParser(), True),
        ),
    ):
        enrich = client.post(f"/companies/{company_id}/enrich?sync=true", headers=headers)

    assert enrich.status_code == 200
    assert enrich.json()["status"] == "completed"

    company = client.get(f"/companies/{company_id}", headers=headers).json()
    assert company["enrichment_status"] == "completed"
    assert company["robots_checked"] is True
    assert company["contact_page_url"] is not None
    assert "email" in (company["enrichment_message"] or "").lower()

    leads = client.get(f"/leads?niche_id={niche_id}", headers=headers).json()
    assert leads["items"][0]["status"] == "enriched"


def test_enrich_company_fails_when_robots_disallow():
    client = get_client()
    headers = auth_headers(client)

    niche_id = client.post(
        "/niches",
        headers=headers,
        json={
            "name": "Blocked Niche",
            "country": "UK",
            "industry": "Healthcare",
            "target_roles": ["Head of People"],
            "keywords": ["NHS"],
            "exclusion_keywords": [],
        },
    ).json()["id"]

    client.post(
        "/leads/import-csv",
        headers=headers,
        files={
            "file": (
                "leads.csv",
                "full_name,job_title,company,website,linkedin_url,email,source_url,"
                "compliance_source_note,niche\n"
                "Jamie Lee,Head of People,Blocked Trust,https://blocked-trust.nhs.uk,,,"
                "https://example.com/source,Public listing,Blocked Niche\n",
                "text/csv",
            ),
        },
    )

    company_id = client.get("/companies", headers=headers).json()["items"][0]["id"]

    with patch(
        "app.services.enrichment.enricher.crawl_company_site",
        return_value=([], "robots.txt disallows fetching the company homepage"),
    ):
        enrich = client.post(f"/companies/{company_id}/enrich?sync=true", headers=headers)

    assert enrich.status_code == 200
    assert enrich.json()["status"] == "failed"
    assert "robots" in enrich.json()["message"].lower()
