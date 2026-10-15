from sqlalchemy import select

from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus
from app.models.suppression import Suppression
from tests.conftest import TestingSessionLocal, get_client
from tests.sending_helpers import approved_message, load_message


def _token(message_id: int) -> str:
    return load_message(message_id).unsubscribe_token


def test_get_only_shows_confirmation():
    client = get_client()
    headers, _campaign_id, (message_id,) = approved_message(client)
    page = client.get(f"/unsubscribe/{_token(message_id)}")
    assert page.status_code == 200
    assert '<form method="post"' in page.text
    assert "default-src 'none'" in page.headers["content-security-policy"]
    # Nothing changed: link scanners following the URL must not unsubscribe anyone.
    assert client.get("/suppressions", headers=headers).json()["total"] == 0


def test_post_suppresses_only_that_address_and_cancels_pending():
    client = get_client()
    headers, _campaign_id, message_ids = approved_message(
        client,
        emails=["jo@gmail.com", "sam@gmail.com"],
    )
    by_email = {load_message(mid).recipient_email: mid for mid in message_ids}
    jo, sam = by_email["jo@gmail.com"], by_email["sam@gmail.com"]
    response = client.post(f"/unsubscribe/{_token(jo)}")
    assert response.status_code == 200
    assert "unsubscribed" in response.text.lower()

    db = TestingSessionLocal()
    try:
        rows = db.scalars(select(Suppression)).all()
        assert [(row.email, row.domain) for row in rows] == [("jo@gmail.com", None)]
    finally:
        db.close()
    # The unsubscribed person's pending email is cancelled; the colleague's is untouched.
    assert load_message(jo).status == EmailMessageStatus.CANCELLED
    assert load_message(sam).status == EmailMessageStatus.APPROVED
    lead_statuses = {
        lead["primary_email"]: lead["status"]
        for lead in client.get("/leads", headers=headers).json()["items"]
    }
    assert lead_statuses["jo@gmail.com"] == "opted_out"
    assert lead_statuses["sam@gmail.com"] != "opted_out"


def test_one_click_post_from_mail_client():
    client = get_client()
    _headers, _campaign_id, (message_id,) = approved_message(client)
    response = client.post(
        f"/unsubscribe/{_token(message_id)}",
        content="List-Unsubscribe=One-Click",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    db = TestingSessionLocal()
    try:
        assert db.scalar(select(Suppression.id)) is not None
    finally:
        db.close()


def test_unknown_token():
    client = get_client()
    assert client.get("/unsubscribe/not-a-real-token").status_code == 404
    assert client.post("/unsubscribe/not-a-real-token").status_code == 404


def test_freemail_domain_cannot_be_suppressed_wholesale():
    client = get_client()
    headers, *_ = approved_message(client)
    response = client.post("/suppressions", headers=headers, json={"domain": "gmail.com"})
    assert response.status_code == 400


def test_opted_out_lead_status_cannot_be_edited_back():
    client = get_client()
    headers, _campaign_id, (message_id,) = approved_message(client)
    client.post(f"/unsubscribe/{_token(message_id)}")
    lead_id = load_message(message_id).lead_id
    response = client.patch(f"/leads/{lead_id}", headers=headers, json={"status": "qualified"})
    assert response.status_code == 400


def test_message_rows_exist():
    db = TestingSessionLocal()
    try:
        db.scalars(select(EmailMessage.id)).all()
    finally:
        db.close()
