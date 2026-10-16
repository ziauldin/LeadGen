from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.enrollment import CampaignEnrollment
from app.models.suppression import Suppression
from app.services.sending.sender import dispatch
from tests.conftest import TestingSessionLocal, auth_headers, get_client
from tests.sending_helpers import ALL_DAYS, CSV_HEADER, STEP

FOLLOW_UP = {
    "step_number": 2,
    "delay_days": 3,
    "subject_template": "x",
    "body_template": "Bumping this. Opt out: {{unsubscribe_link}}",
}


def drafts(client, count=3, *, verify=True):
    """A campaign with ``count`` leads enrolled and their first drafts waiting for review."""
    headers = auth_headers(client, verify=verify)
    niche_id = client.post(
        "/niches",
        headers=headers,
        json={"name": "Queue Niche", "country": "UK", "industry": "Food", "target_roles": ["QM"]},
    ).json()["id"]
    client.patch(
        "/settings",
        headers=headers,
        json={"sender_name": "Sam", "sender_company": "Acme Ltd", "business_address": "London"},
    )
    rows = "".join(
        f"Person {i},Quality Manager,Company {i},https://company-{i}.co.uk,,person{i}@company-{i}.co.uk,"
        "https://example.com/listing,Public listing,Queue Niche\n"
        for i in range(count)
    )
    client.post(
        "/leads/import-csv",
        headers=headers,
        files={"file": ("l.csv", CSV_HEADER + rows, "text/csv")},
    )
    lead_ids = [lead["id"] for lead in client.get("/leads", headers=headers).json()["items"]]
    campaign_id = client.post(
        "/campaigns",
        headers=headers,
        json={
            "niche_id": niche_id,
            "name": "Queue campaign",
            "sending_window_start": "00:00",
            "sending_window_end": "23:59",
            "sending_days": ALL_DAYS,
            "steps": [STEP, FOLLOW_UP],
        },
    ).json()["id"]
    added = client.post(
        f"/campaigns/{campaign_id}/add-leads",
        headers=headers,
        json={"lead_ids": lead_ids},
    ).json()
    return headers, campaign_id, added["message_ids"], lead_ids, niche_id


def test_queue_lists_drafts_with_live_checks():
    client = get_client()
    headers, campaign_id, message_ids, _leads, _niche = drafts(client)
    queue = client.get("/approvals", headers=headers).json()
    assert queue["total"] == 3
    assert queue["by_campaign"] == {str(campaign_id): 3}
    item = queue["items"][0]
    assert item["campaign_name"] == "Queue campaign"
    assert item["lead"]["company_name"].startswith("Company")
    assert item["can_approve"] is True and item["problems"] == []

    # Suppressing a recipient shows up immediately as a problem.
    target = next(i for i in queue["items"] if i["id"] == message_ids[0])
    db = TestingSessionLocal()
    try:
        db.add(
            Suppression(
                workspace_id=db.scalar(select(CampaignEnrollment.workspace_id)),
                email=target["recipient_email"],
                reason="test",
                source="manual",
            ),
        )
        db.commit()
    finally:
        db.close()
    item = client.get(f"/emails/{message_ids[0]}", headers=headers).json()
    assert item["can_approve"] is False
    assert item["problems"]

    filtered = client.get(
        f"/approvals?campaign_id={campaign_id}&sort=-step_number", headers=headers
    )
    assert filtered.status_code == 200
    assert client.get("/approvals?sort=bogus", headers=headers).status_code == 400


def test_edit_keeps_opt_out_and_records_who_edited():
    client = get_client()
    headers, _cid, message_ids, _leads, _niche = drafts(client, 1)
    message_id = message_ids[0]

    no_opt_out = client.patch(
        f"/emails/{message_id}",
        headers=headers,
        json={"body": "Hi there, fancy a chat?"},
    )
    assert no_opt_out.status_code == 400

    edited = client.patch(
        f"/emails/{message_id}",
        headers=headers,
        json={
            "subject": "A better subject",
            "body": 'Hi, worth a chat? If this is not relevant, reply "not relevant".',
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["subject"] == "A better subject"
    assert edited.json()["edited_at"] is not None


def test_approve_and_reject_single_messages():
    client = get_client()
    headers, campaign_id, message_ids, _leads, _niche = drafts(client, 2)

    approved = client.post(f"/emails/{message_ids[0]}/approve", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    rejected = client.post(
        f"/emails/{message_ids[1]}/reject",
        headers=headers,
        json={"reason": "Wrong contact"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    enrollments = client.get(f"/campaigns/{campaign_id}/enrollments", headers=headers).json()
    stopped = [e for e in enrollments["items"] if e["status"] == "stopped"]
    assert len(stopped) == 1
    assert "Wrong contact" in stopped[0]["stopped_reason"]

    assert client.get("/approvals", headers=headers).json()["total"] == 0
    again = client.post(f"/emails/{message_ids[0]}/reject", headers=headers, json={})
    assert again.status_code == 400


def test_bulk_approve_reports_each_message():
    client = get_client()
    headers, _cid, message_ids, _leads, _niche = drafts(client, 3)
    client.post(f"/emails/{message_ids[2]}/reject", headers=headers, json={})

    result = client.post(
        "/approvals/bulk-approve",
        headers=headers,
        json={"message_ids": [*message_ids, 999_999]},
    ).json()
    assert result["succeeded"] == 2
    assert result["failed"] == 1
    assert result["skipped"] == 1
    statuses = {r["id"]: r["status"] for r in result["results"]}
    assert statuses[message_ids[2]] == "failed"
    assert statuses[999_999] == "skipped"

    db = TestingSessionLocal()
    try:
        assert db.scalar(select(AuditLog).where(AuditLog.action == "email.bulk_approved"))
    finally:
        db.close()

    # Approved messages go out through the normal pipeline.
    db = TestingSessionLocal()
    db.info["tenant_bypass"] = True
    try:
        assert dispatch(db)["queued"] == 0  # campaign not started yet
    finally:
        db.close()


def test_bulk_reject_and_unverified_users_cannot_approve():
    client = get_client()
    headers, _cid, message_ids, _leads, _niche = drafts(client, 2)
    result = client.post(
        "/approvals/bulk-reject",
        headers=headers,
        json={"message_ids": message_ids, "reason": "Not now"},
    ).json()
    assert result["succeeded"] == 2

    client2 = get_client()
    headers2, _cid, message_ids2, _leads, _niche = drafts(client2, 1, verify=False)
    blocked = client2.post(
        "/approvals/bulk-approve",
        headers=headers2,
        json={"message_ids": message_ids2},
    )
    assert blocked.status_code == 403
    assert client2.post(f"/emails/{message_ids2[0]}/approve", headers=headers2).status_code == 403


def test_other_workspaces_cannot_see_or_touch_drafts():
    client = get_client()
    _headers, _cid, message_ids, _leads, _niche = drafts(client, 1)
    other = auth_headers(client, email="intruder@example.com")
    assert client.get("/approvals", headers=other).json()["total"] == 0
    assert client.get(f"/emails/{message_ids[0]}", headers=other).status_code == 404
    assert (
        client.patch(f"/emails/{message_ids[0]}", headers=other, json={"subject": "x"}).status_code
        == 404
    )
    result = client.post(
        "/approvals/bulk-approve",
        headers=other,
        json={"message_ids": message_ids},
    ).json()
    assert result["skipped"] == 1 and result["succeeded"] == 0
