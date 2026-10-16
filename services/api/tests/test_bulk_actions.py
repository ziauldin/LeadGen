from datetime import UTC, datetime

from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus
from app.models.reply import Reply
from app.services.deliverability import LookupFailedError, run_checks, valid_domain
from app.services.sending.sender import dispatch
from tests.conftest import TestingSessionLocal, auth_headers, get_client
from tests.test_approvals import drafts


def _bulk(client, headers, **payload):
    return client.post("/leads/bulk", headers=headers, json=payload)


def test_bulk_set_status_rescore_and_delete():
    client = get_client()
    headers, _cid, _mids, lead_ids, _niche = drafts(client, 3)

    result = _bulk(client, headers, lead_ids=lead_ids, action="set_status", status="qualified")
    assert result.json()["succeeded"] == 3

    opted_out = _bulk(
        client, headers, lead_ids=lead_ids[:1], action="set_status", status="opted_out"
    )
    assert opted_out.json()["failed"] == 1

    rescored = _bulk(client, headers, lead_ids=lead_ids, action="rescore").json()
    assert rescored["succeeded"] == 3

    deleted = _bulk(client, headers, lead_ids=[lead_ids[0], 424242], action="delete").json()
    assert (deleted["succeeded"], deleted["skipped"]) == (1, 1)
    assert client.get("/leads", headers=headers).json()["total"] == 2


def test_bulk_validation():
    client = get_client()
    headers = auth_headers(client)
    assert _bulk(client, headers, lead_ids=[1], action="add_to_campaign").status_code == 422
    assert _bulk(client, headers, lead_ids=[1], action="set_status").status_code == 422
    assert _bulk(client, headers, lead_ids=list(range(501)), action="rescore").status_code == 422
    assert _bulk(client, headers, lead_ids=[1], action="explode").status_code == 422


def test_bulk_add_to_campaign_reports_each_lead():
    client = get_client()
    headers, campaign_id, _mids, lead_ids, niche_id = drafts(client, 2)
    second = client.post(
        "/campaigns",
        headers=headers,
        json={
            "niche_id": niche_id,
            "name": "Second",
            "steps": [{"step_number": 1, "template_id": "system:intro"}],
        },
    ).json()["id"]
    first = _bulk(
        client, headers, lead_ids=lead_ids, action="add_to_campaign", campaign_id=second
    ).json()
    assert first["succeeded"] == 2
    again = _bulk(
        client, headers, lead_ids=lead_ids, action="add_to_campaign", campaign_id=second
    ).json()
    assert again["skipped"] == 2
    assert {r["detail"] for r in again["results"]} == {"Already in this campaign"}

    other = auth_headers(client, email="other@example.com")
    foreign = _bulk(
        client, other, lead_ids=lead_ids, action="add_to_campaign", campaign_id=campaign_id
    )
    assert foreign.status_code == 404


def test_bulk_enrich_dedupes_companies_and_respects_quota():
    client = get_client()
    headers, _cid, _mids, lead_ids, _niche = drafts(client, 2)
    result = _bulk(client, headers, lead_ids=lead_ids, action="enrich").json()
    assert result["succeeded"] == 2, result

    companies = client.get("/companies?sort=-name", headers=headers).json()["items"]
    assert [c["name"] for c in companies] == ["Company 1", "Company 0"]
    bulk = client.post(
        "/companies/bulk-enrich",
        headers=headers,
        json={"ids": [c["id"] for c in companies] + [999_999]},
    ).json()
    assert bulk["succeeded"] + bulk["failed"] + bulk["skipped"] == 3
    assert any(r["id"] == 999_999 and r["status"] == "skipped" for r in bulk["results"])


def test_lead_stats_filters_and_sorting():
    client = get_client()
    headers, _cid, _mids, _lead_ids, _niche = drafts(client, 3)
    stats = client.get("/leads/stats", headers=headers).json()
    assert stats["total"] == 3
    assert stats["with_email"] == 3
    assert stats["added_last_7_days"] == 3
    assert stats["in_active_sequences"] == 3

    by_name = client.get("/leads?sort=full_name", headers=headers).json()["items"]
    assert [lead["full_name"] for lead in by_name] == ["Person 0", "Person 1", "Person 2"]
    by_company = client.get("/leads?search=Company 2", headers=headers).json()
    assert by_company["total"] == 1
    assert client.get("/leads?has_email=false", headers=headers).json()["total"] == 0
    assert client.get("/leads?sort=password", headers=headers).status_code == 400


def test_campaign_metrics_and_messages():
    client = get_client()
    headers, campaign_id, message_ids, _leads, _niche = drafts(client, 3)
    client.post("/approvals/bulk-approve", headers=headers, json={"message_ids": message_ids})
    client.post(f"/campaigns/{campaign_id}/start", headers=headers)
    db = TestingSessionLocal()
    db.info["tenant_bypass"] = True
    try:
        dispatch(db, now=datetime.now(UTC))
        bounced = db.get(EmailMessage, message_ids[0])
        bounced.status = EmailMessageStatus.BOUNCED
        replied = db.get(EmailMessage, message_ids[1])
        db.add(
            Reply(
                workspace_id=replied.workspace_id,
                email_message_id=replied.id,
                from_email=replied.recipient_email,
                body="Sounds good",
                classification="positive",
                received_at=datetime.now(UTC),
            ),
        )
        db.commit()
    finally:
        db.close()

    metrics = client.get(f"/campaigns/{campaign_id}/metrics", headers=headers).json()
    assert metrics["sent"] == 3
    assert metrics["bounced"] == 1
    assert metrics["replies"] == 1 and metrics["positive_replies"] == 1
    assert metrics["reply_rate"] == round(1 / 3, 4)
    assert metrics["steps"][0]["step_number"] == 1 and metrics["steps"][0]["sent"] == 3
    assert metrics["steps"][1]["drafts"] == 0

    messages = client.get(
        f"/campaigns/{campaign_id}/messages?status=bounced",
        headers=headers,
    ).json()
    assert messages["total"] == 1
    assert messages["items"][0]["lead_name"].startswith("Person")
    assert (
        client.get(
            f"/campaigns/{campaign_id}/metrics", headers=auth_headers(client, email="x@y.co")
        ).status_code
        == 404
    )


def test_campaign_steps_can_be_edited_but_used_steps_stay():
    client = get_client()
    headers, campaign_id, _mids, _leads, _niche = drafts(client, 1)
    edited = client.patch(
        f"/campaigns/{campaign_id}",
        headers=headers,
        json={
            "steps": [
                {
                    "step_number": 1,
                    "subject_template": "New subject {{company}}",
                    "body_template": "Hi. Opt out: {{unsubscribe_link}}",
                },
                {"step_number": 3, "delay_days": 7, "template_id": "system:follow-up"},
            ],
        },
    )
    assert edited.status_code == 200, edited.text
    steps = {s["step_number"]: s for s in edited.json()["steps"]}
    assert set(steps) == {1, 3}
    assert steps[1]["subject_template"] == "New subject {{company}}"
    assert steps[3]["template_id"] == "system:follow-up"

    removing_used = client.patch(
        f"/campaigns/{campaign_id}",
        headers=headers,
        json={"steps": [{"step_number": 3, "template_id": "system:follow-up"}]},
    )
    assert removing_used.status_code == 400
    duplicate = client.patch(
        f"/campaigns/{campaign_id}",
        headers=headers,
        json={"steps": [{"step_number": 1, "template_id": "system:intro"}] * 2},
    )
    assert duplicate.status_code == 422


# --- deliverability ---------------------------------------------------------------------------

GOOD_DNS = {
    ("acme.co.uk", "TXT"): ["v=spf1 include:amazonses.com ~all", "google-site-verification=x"],
    ("_dmarc.acme.co.uk", "TXT"): ["v=DMARC1; p=quarantine; rua=mailto:d@acme.co.uk"],
    ("resend._domainkey.acme.co.uk", "TXT"): ["p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC"],
    ("acme.co.uk", "MX"): ["10 mx.acme.co.uk."],
}


def fake_lookup(table):
    def lookup(name, rdtype):
        value = table.get((name, rdtype))
        if isinstance(value, Exception):
            raise value
        return value or []

    return lookup


def test_deliverability_all_good():
    report = run_checks("acme.co.uk", provider="resend", lookup=fake_lookup(GOOD_DNS))
    assert report["overall"] == "pass"
    assert [c["status"] for c in report["checks"]] == ["pass"] * 4


def test_deliverability_finds_problems():
    table = {
        ("acme.co.uk", "TXT"): ["v=spf1 +all"],
        ("_dmarc.acme.co.uk", "TXT"): ["v=DMARC1; p=none"],
        ("acme.co.uk", "MX"): LookupFailedError("timeout"),
    }
    report = run_checks("acme.co.uk", inbound_domain="in.acme.co.uk", lookup=fake_lookup(table))
    by_name = {c["name"]: c for c in report["checks"]}
    assert by_name["SPF"]["status"] == "fail"
    assert by_name["DMARC"]["status"] == "warn"
    assert by_name["DKIM"]["status"] == "warn"
    assert by_name["MX"]["status"] == "unknown"
    assert by_name["Inbound replies"]["status"] == "fail"
    assert report["overall"] == "fail"


def test_deliverability_endpoint_validates_domain(monkeypatch):
    client = get_client()
    headers = auth_headers(client)
    assert client.get("/settings/deliverability", headers=headers).status_code == 400
    assert (
        client.get("/settings/deliverability?domain=not a domain", headers=headers).status_code
        == 400
    )
    assert not valid_domain("localhost")
    monkeypatch.setattr(
        "app.api.routes.settings.run_checks",
        lambda domain, **kw: run_checks(domain, lookup=fake_lookup(GOOD_DNS), **kw),
    )
    report = client.get("/settings/deliverability?domain=acme.co.uk", headers=headers).json()
    assert report["domain"] == "acme.co.uk"
    assert {c["name"] for c in report["checks"]} >= {"SPF", "DKIM", "DMARC", "MX"}


def test_leads_that_were_emailed_cannot_be_deleted():
    client = get_client()
    headers, campaign_id, message_ids, lead_ids, _niche = drafts(client, 2)
    client.post("/approvals/bulk-approve", headers=headers, json={"message_ids": message_ids})
    client.post(f"/campaigns/{campaign_id}/start", headers=headers)
    db = TestingSessionLocal()
    db.info["tenant_bypass"] = True
    try:
        dispatch(db, now=datetime.now(UTC))
        sent_lead = db.get(EmailMessage, message_ids[0]).lead_id
    finally:
        db.close()
    assert client.delete(f"/leads/{sent_lead}", headers=headers).status_code == 400
    result = _bulk(client, headers, lead_ids=lead_ids, action="delete").json()
    assert result["failed"] == 2  # both were sent by the dispatcher


def test_search_can_pick_a_configured_provider_or_mock():
    client = get_client()
    headers = auth_headers(client)
    niche_id = client.post(
        "/niches",
        headers=headers,
        json={"name": "N", "country": "UK", "industry": "Food", "target_roles": ["QM"]},
    ).json()["id"]
    run = client.post(
        "/searches/run",
        headers=headers,
        json={"niche_id": niche_id, "query": "food quality manager", "provider": "mock"},
    )
    assert run.status_code == 201, run.text
    assert run.json()["provider"] == "mock"
    missing = client.post(
        "/searches/run",
        headers=headers,
        json={"niche_id": niche_id, "query": "x", "provider": "serpapi"},
    )
    assert missing.status_code == 400
    assert "serpapi" in missing.json()["detail"]
