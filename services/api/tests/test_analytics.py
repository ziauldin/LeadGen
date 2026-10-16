import csv
import io
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus, ReplyClassification
from app.models.reply import Reply
from app.services.analytics.service import (
    choose_variant,
    two_proportion_p_value,
    variant_results,
)
from tests.conftest import TestingSessionLocal, auth_headers, get_client
from tests.sending_helpers import STEP, approved_message

VARIANT_B = {
    "key": "B",
    "subject_template": "Idea for {{company}}",
    "body_template": STEP["body_template"],
}


@pytest.fixture(autouse=True)
def analytics_on(monkeypatch):
    monkeypatch.setattr(settings, "feature_analytics_v2", True)


def _db():
    db = TestingSessionLocal()
    db.info["tenant_bypass"] = True
    return db


def _send_all(campaign_id, *, bounce=(), reply=(), positive=()):
    """Mark the campaign's emails sent; add replies to the given positions."""
    db = _db()
    try:
        messages = db.scalars(
            select(EmailMessage)
            .where(EmailMessage.campaign_id == campaign_id)
            .order_by(EmailMessage.id)
        ).all()
        now = datetime.now(UTC)
        for i, message in enumerate(messages):
            message.status = EmailMessageStatus.BOUNCED if i in bounce else EmailMessageStatus.SENT
            message.sent_at = now
            if i in reply or i in positive:
                db.add(
                    Reply(
                        workspace_id=message.workspace_id,
                        email_message_id=message.id,
                        lead_id=message.lead_id,
                        from_email=message.recipient_email,
                        body="Yes please" if i in positive else "Not now",
                        classification=(
                            ReplyClassification.POSITIVE
                            if i in positive
                            else ReplyClassification.NEUTRAL
                        ),
                        received_at=now,
                    )
                )
        db.commit()
        return [(m.id, m.variant, m.subject) for m in messages]
    finally:
        db.close()


def test_choose_variant_is_even_and_stable():
    step = SimpleNamespace(
        variants=[VARIANT_B, {"key": "C", "subject_template": "", "body_template": "x"}]
    )
    # The incomplete C version is ignored: an even A/B split.
    picks = [choose_variant(step, seed)[0] for seed in range(100)]  # type: ignore[arg-type]
    assert picks.count("A") == 50 and picks.count("B") == 50
    assert choose_variant(step, 7) == choose_variant(step, 7)  # type: ignore[arg-type]
    assert choose_variant(SimpleNamespace(variants=None), 3) == ("A", None)  # type: ignore[arg-type]


def test_p_value():
    assert two_proportion_p_value(0, 0, 1, 10) is None
    assert two_proportion_p_value(0, 50, 0, 50) == 1.0
    same = two_proportion_p_value(10, 100, 10, 100)
    assert same is not None and same > 0.99
    clear = two_proportion_p_value(30, 100, 5, 100)
    assert clear is not None and clear < 0.001


def test_variants_are_used_and_counted():
    client = get_client()
    emails = [f"person{i}@company-{i}.co.uk" for i in range(4)]
    headers, campaign_id, _ids = approved_message(
        client, emails=emails, campaign_overrides={"steps": [{**STEP, "variants": [VARIANT_B]}]}
    )
    step = client.get(f"/campaigns/{campaign_id}", headers=headers).json()["steps"][0]
    assert step["variants"][0]["key"] == "B"

    sent = _send_all(campaign_id, bounce={0}, positive={1})
    variants = {v for _id, v, _subject in sent}
    assert variants == {"A", "B"}
    for _id, variant, subject in sent:
        assert subject.startswith("Idea for" if variant == "B" else "Quick question")

    results = client.get(f"/campaigns/{campaign_id}/variants", headers=headers).json()
    assert len(results) == 1 and results[0]["step_number"] == 1
    by_key = {v["variant"]: v for v in results[0]["variants"]}
    assert sum(v["sent"] for v in by_key.values()) == 4
    assert sum(v["bounced"] for v in by_key.values()) == 1
    assert sum(v["positive"] for v in by_key.values()) == 1
    assert results[0]["winner"] is None  # far too few sends to call it

    overview = client.get("/analytics/overview?days=7", headers=headers).json()
    assert overview["totals"]["sent"] == 4 and overview["totals"]["replies"] == 1
    assert overview["totals"]["reply_rate"] == 0.25
    assert len(overview["series"]) == 7 and overview["series"][-1]["sent"] == 4
    assert overview["by_campaign"][0]["label"] == "Send campaign"
    assert {row["label"] for row in overview["by_variant"]} == {"A", "B"}
    assert overview["by_step"][0]["label"] == "Step 1"
    assert overview["by_mailbox"][0]["label"] == "Default sender"

    filtered = client.get(f"/analytics/overview?campaign_id={campaign_id}", headers=headers).json()
    assert filtered["totals"]["sent"] == 4

    other = auth_headers(client, "other@example.com")
    assert client.get("/analytics/overview", headers=other).json()["totals"]["sent"] == 0
    assert client.get(f"/campaigns/{campaign_id}/variants", headers=other).status_code == 404
    assert (
        client.get(f"/analytics/overview?campaign_id={campaign_id}", headers=other).status_code
        == 404
    )


def test_winner_needs_enough_sends_and_significance():
    client = get_client()
    headers, campaign_id, _ids = approved_message(client)
    db = _db()
    try:
        template = db.scalar(select(EmailMessage).where(EmailMessage.campaign_id == campaign_id))
        assert template is not None
        workspace_id = template.workspace_id
        now = datetime.now(UTC)
        # A: 40 sends, 2 replies. B: 40 sends, 16 replies.
        for variant, replies in (("A", 2), ("B", 16)):
            for i in range(40):
                message = EmailMessage(
                    workspace_id=workspace_id,
                    campaign_id=campaign_id,
                    lead_id=template.lead_id,
                    step_number=1,
                    variant=variant,
                    recipient_email=template.recipient_email,
                    subject="s",
                    body="b",
                    status=EmailMessageStatus.SENT,
                    sent_at=now,
                )
                db.add(message)
                db.flush()
                if i < replies:
                    db.add(
                        Reply(
                            workspace_id=workspace_id,
                            email_message_id=message.id,
                            from_email=template.recipient_email,
                            body="Yes",
                            classification=ReplyClassification.POSITIVE,
                            received_at=now,
                        )
                    )
        db.commit()
        results = variant_results(db, workspace_id, campaign_id)
    finally:
        db.close()
    assert results[0]["winner"]["variant"] == "B"
    assert results[0]["winner"]["p_value"] < 0.05
    api = client.get(f"/campaigns/{campaign_id}/variants", headers=headers).json()
    assert api[0]["winner"]["variant"] == "B"


def test_variant_validation():
    client = get_client()
    headers = auth_headers(client)
    niche_id = client.post(
        "/niches",
        headers=headers,
        json={"name": "N", "country": "UK", "industry": "Food", "target_roles": ["QM"]},
    ).json()["id"]
    body = {
        "niche_id": niche_id,
        "name": "Dup",
        "steps": [{**STEP, "variants": [VARIANT_B, VARIANT_B]}],
    }
    assert client.post("/campaigns", headers=headers, json=body).status_code == 422
    body["steps"] = [{**STEP, "variants": [{**VARIANT_B, "key": "A"}]}]
    assert client.post("/campaigns", headers=headers, json=body).status_code == 422


def test_export_csv_and_flag(monkeypatch):
    client = get_client()
    headers, campaign_id, _ids = approved_message(client)
    _send_all(campaign_id, reply={0})
    response = client.get("/analytics/export?days=3", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 3 and rows[-1]["sent"] == "1" and rows[-1]["replies"] == "1"

    monkeypatch.setattr(settings, "feature_analytics_v2", False)
    assert client.get("/analytics/overview", headers=headers).status_code == 404
    assert client.get("/analytics/export", headers=headers).status_code == 404
    # Per-campaign A/B results stay available: they're part of the campaign page.
    assert client.get(f"/campaigns/{campaign_id}/variants", headers=headers).status_code == 200


def test_weekly_digest_includes_analytics():
    from app.services.notifications import lifecycle
    from app.services.platform_email.mailer import OUTBOX

    client = get_client()
    _headers, campaign_id, _ids = approved_message(client)
    _send_all(campaign_id, positive={0})
    db = TestingSessionLocal()
    try:
        OUTBOX.clear()
        assert lifecycle.weekly_digest(db) == 1
    finally:
        db.close()
    digest = next(m for m in OUTBOX if m.tags.get("kind") == "lifecycle:digest")
    assert "Reply rate: 100.0% (interested 100.0%)" in digest.text
    assert "/analytics" in digest.text
