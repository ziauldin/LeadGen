import httpx
import pytest
from sqlalchemy import select

from app.models.email_contact import EmailContact
from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus
from app.models.workspace import Workspace
from app.services.verification import providers
from app.services.verification.providers import (
    INVALID,
    RISKY,
    UNKNOWN,
    VALID,
    DnsVerifier,
    MockVerifier,
    NeverBounceVerifier,
    ZeroBounceVerifier,
)
from tests.conftest import TestingSessionLocal, get_client
from tests.sending_helpers import approved_message

LEADS = (
    "alex@example-foods.co.uk",
    "invalid.person@example-foods.co.uk",
    "risky@example-foods.co.uk",
)


def _connect_mock_verifier(client, headers):
    created = client.post(
        "/provider-settings",
        headers=headers,
        json={
            "provider_type": "email_verification",
            "provider_name": "mock",
            "display_name": "Mock",
            "config": {},
        },
    )
    assert created.status_code in (200, 201), created.text
    credential_id = created.json()["id"]
    activated = client.patch(f"/provider-settings/{credential_id}/activate", headers=headers)
    assert activated.status_code == 200, activated.text


def _contacts():
    db = TestingSessionLocal()
    try:
        return {c.email: c for c in db.scalars(select(EmailContact)).all()}
    finally:
        db.close()


def test_mock_and_dns_verifiers():
    mock = MockVerifier()
    assert mock.verify("jo@acme.co.uk").status == VALID
    assert mock.verify("invalid@acme.co.uk").status == INVALID
    assert mock.verify("catchall@acme.co.uk").status == RISKY
    assert mock.verify("not-an-email").status == INVALID

    class Resolver:
        lifetime = 0

        def __init__(self, answers):
            self.answers = answers

        def resolve(self, domain, record):
            import dns.resolver

            if domain in self.answers:
                return [object()]
            raise dns.resolver.NXDOMAIN()

    dns_check = DnsVerifier(Resolver({"acme.co.uk"}))
    assert dns_check.verify("jo@acme.co.uk").status == UNKNOWN
    assert dns_check.verify("jo@nowhere-at-all.invalid").status == INVALID
    assert dns_check.verify("jo@mailinator.com").status == RISKY
    assert dns_check.verify("jo@acme.co.uk").billable is False


def test_zerobounce_and_neverbounce_mapping(monkeypatch):
    answers = {
        "api.zerobounce.net": {"status": "catch-all", "sub_status": ""},
        "api.neverbounce.com": {"status": "success", "result": "disposable"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=answers[request.url.host])

    monkeypatch.setattr(
        providers, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert ZeroBounceVerifier("key").verify("a@b.co").status == RISKY
    assert NeverBounceVerifier("key").verify("a@b.co").status == INVALID
    answers["api.zerobounce.net"] = {"error": "Invalid API key"}
    result = ZeroBounceVerifier("bad").verify("a@b.co")
    assert result.status == UNKNOWN and result.billable is False


def test_bulk_verify_and_gate(monkeypatch):
    client = get_client()
    headers, campaign_id, _message_ids = approved_message(client, emails=LEADS)
    _connect_mock_verifier(client, headers)
    lead_ids = [lead["id"] for lead in client.get("/leads", headers=headers).json()["items"]]
    response = client.post(
        "/leads/bulk", headers=headers, json={"action": "verify", "lead_ids": lead_ids}
    )
    assert response.status_code == 200, response.text
    assert response.json()["succeeded"] == 3

    contacts = _contacts()
    assert contacts["alex@example-foods.co.uk"].verification_status == VALID
    assert contacts["invalid.person@example-foods.co.uk"].verification_status == INVALID
    assert contacts["risky@example-foods.co.uk"].verification_status == RISKY

    lead = client.get(f"/leads/{lead_ids[0]}", headers=headers).json()
    assert lead["email_contacts"][0]["verification_status"] in (VALID, INVALID, RISKY)

    # Invalid addresses are blocked; risky ones only when the workspace says so.
    assert (
        client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers).json()["sent"] == 2
    )
    db = TestingSessionLocal()
    try:
        statuses = {m.recipient_email: m.status for m in db.scalars(select(EmailMessage)).all()}
        assert statuses["invalid.person@example-foods.co.uk"] == EmailMessageStatus.CANCELLED
        assert statuses["risky@example-foods.co.uk"] == EmailMessageStatus.SENT
    finally:
        db.close()

    client.patch("/settings", headers=headers, json={"block_risky_emails": True})
    assert client.get("/settings", headers=headers).json()["block_risky_emails"] is True
    risky_lead = next(
        lead["id"]
        for lead in client.get("/leads", headers=headers).json()["items"]
        if lead["primary_email"] == "risky@example-foods.co.uk"
    )
    readiness = client.get(f"/leads/{risky_lead}/outreach-readiness", headers=headers).json()
    assert readiness["ready"] is False
    assert any("risky" in issue.lower() for issue in readiness["issues"])


def test_verification_uses_plan_credits():
    client = get_client()
    headers, _campaign, _ids = approved_message(client, emails=LEADS)
    _connect_mock_verifier(client, headers)
    db = TestingSessionLocal()
    try:
        workspace = db.scalar(select(Workspace))
        workspace.plan_overrides = {"monthly_verifications": 2}
        db.commit()
    finally:
        db.close()
    lead_ids = [lead["id"] for lead in client.get("/leads", headers=headers).json()["items"]]
    client.post("/leads/bulk", headers=headers, json={"action": "verify", "lead_ids": lead_ids})
    checked = [c for c in _contacts().values() if c.verification_status is not None]
    assert len(checked) == 2
    usage = {u["metric"]: u for u in client.get("/billing", headers=headers).json()["usage"]}
    assert usage["monthly_verifications"]["used"] == 2


def test_new_contacts_are_verified_automatically_with_a_provider():
    client = get_client()
    from tests.conftest import auth_headers

    headers = auth_headers(client)
    client.post(
        "/niches", headers=headers, json={"name": "Send Niche", "country": "UK", "industry": "Food"}
    )
    _connect_mock_verifier(client, headers)
    csv = (
        "full_name,job_title,company,website,linkedin_url,email,source_url,compliance_source_note,niche\n"
        "Pat,QM,Co,https://co.co.uk,,bounce.pat@co.co.uk,https://example.com,Listing,Send Niche\n"
    )
    client.post("/leads/import-csv", headers=headers, files={"file": ("l.csv", csv, "text/csv")})
    assert _contacts()["bounce.pat@co.co.uk"].verification_status == INVALID


@pytest.mark.parametrize("value", ["block", None])
def test_settings_toggle_validation(value):
    client = get_client()
    from tests.conftest import auth_headers

    headers = auth_headers(client)
    response = client.patch("/settings", headers=headers, json={"block_risky_emails": value})
    assert response.status_code == (422 if value == "block" else 200)
