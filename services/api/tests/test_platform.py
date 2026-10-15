from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.errors import NotFoundError, QuotaExceededError
from app.main import app
from tests.conftest import auth_headers, get_client

_router = APIRouter()


@_router.get("/__test/boom")
def _boom() -> None:
    raise RuntimeError("secret internal detail")


@_router.get("/__test/quota")
def _quota() -> None:
    raise QuotaExceededError("monthly_sends", 100, 100)


@_router.get("/__test/missing")
def _missing() -> None:
    raise NotFoundError("Widget not found")


app.include_router(_router)

CSV = (
    "full_name,job_title,company,website,linkedin_url,email,source_url,compliance_source_note,niche\n"
    "A B,CEO,Acme,https://acme.example,,,https://s.example,n,N\n"
)


def test_request_id_is_generated_and_echoed():
    client = get_client()
    response = client.get("/health")
    assert len(response.headers["x-request-id"]) >= 8
    echoed = client.get("/health", headers={"X-Request-ID": "abc12345-req"})
    assert echoed.headers["x-request-id"] == "abc12345-req"


def test_security_headers_present():
    response = get_client().get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_unhandled_errors_do_not_leak_details():
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/__test/boom")
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
    assert "secret internal detail" not in response.text
    assert response.json()["request_id"]


def test_app_errors_map_to_status_codes():
    client = get_client()
    quota = client.get("/__test/quota")
    assert quota.status_code == 402
    assert quota.json()["metric"] == "monthly_sends"
    assert client.get("/__test/missing").status_code == 404


def test_enrich_returns_503_when_broker_is_down(monkeypatch):
    client = get_client()
    headers = auth_headers(client)
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
    company_id = client.get("/companies", headers=headers).json()["items"][0]["id"]

    def broken_delay(*_args, **_kwargs):
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.workers.enrichment_jobs.enrich_company.delay", broken_delay)
    response = client.post(f"/companies/{company_id}/enrich", headers=headers)
    assert response.status_code == 503
    company = client.get(f"/companies/{company_id}", headers=headers).json()
    assert company["enrichment_status"] == "pending"
