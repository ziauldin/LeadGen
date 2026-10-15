from email import message_from_bytes

from app.core.config import settings
from app.models.email_message import EmailMessage
from app.models.workspace import WorkspaceSettings
from app.services.sending.external_providers import SmtpEmailSender
from app.services.sending.mime import build_outbound, text_to_html
from app.services.sending.mock_provider import MOCK_OUTBOX
from tests.conftest import TestingSessionLocal, get_client
from tests.sending_helpers import approved_message


def _message(**overrides) -> EmailMessage:
    defaults = {
        "id": 42,
        "workspace_id": 1,
        "recipient_email": "jo@client.co.uk",
        "subject": "Hello",
        "body": "Hi Jo,\n\nVisit https://acme.example/info for more.\n\nSam",
        "unsubscribe_token": "tok123",
        "reply_token": "rt456",
        "rfc_message_id": "lg.abc@acme.example",
        "idempotency_key": "lg-1-42-x",
    }
    defaults.update(overrides)
    return EmailMessage(**defaults)


def test_headers_footer_and_html(monkeypatch):
    monkeypatch.setattr(settings, "inbound_email_domain", "in.leadsgen.app")
    settings_row = WorkspaceSettings(sender_company="Acme Ltd", business_address="1 High St")
    outbound = build_outbound(
        _message(),
        from_email="sam@acme.example",
        workspace_settings=settings_row,
        in_reply_to="lg.first@acme.example",
    )
    assert outbound.message_id == "lg.abc@acme.example"
    assert outbound.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "/unsubscribe/tok123>" in outbound.headers["List-Unsubscribe"]
    assert "mailto:unsubscribe+tok123@in.leadsgen.app" in outbound.headers["List-Unsubscribe"]
    assert outbound.headers["Reply-To"] == "reply+rt456@in.leadsgen.app"
    assert outbound.headers["In-Reply-To"] == "<lg.first@acme.example>"
    # Footer with postal address and unsubscribe link is always added by the server.
    assert "Acme Ltd, 1 High St" in outbound.text
    assert "Unsubscribe: " in outbound.text
    assert '<a href="https://acme.example/info">' in outbound.html
    assert "<script" not in text_to_html("<script>alert(1)</script>")


def test_no_reply_to_without_inbound_domain(monkeypatch):
    monkeypatch.setattr(settings, "inbound_email_domain", "")
    outbound = build_outbound(_message(), from_email="sam@acme.example", workspace_settings=None)
    assert "Reply-To" not in outbound.headers
    assert outbound.headers["List-Unsubscribe"].count("<") == 1


def test_smtp_message_is_multipart_with_headers(monkeypatch):
    monkeypatch.setattr(settings, "inbound_email_domain", "in.leadsgen.app")
    outbound = build_outbound(_message(), from_email="sam@acme.example", workspace_settings=None)
    sender = SmtpEmailSender(
        host="smtp.example",
        port=587,
        username="",
        password="",
        from_email="sam@acme.example",
        from_name="Sam",
    )
    parsed = message_from_bytes(sender.build_mime(outbound).as_bytes())
    assert parsed["Message-ID"] == "<lg.abc@acme.example>"
    assert parsed["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert parsed.is_multipart()
    assert {part.get_content_type() for part in parsed.walk()} >= {"text/plain", "text/html"}


def test_sent_mail_contains_footer_end_to_end():
    MOCK_OUTBOX.clear()
    client = get_client()
    headers, campaign_id, _ = approved_message(client)
    client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers)
    sent = MOCK_OUTBOX[-1]
    assert "Acme Ltd, 1 High St, London" in sent.text
    assert sent.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    db = TestingSessionLocal()
    db.close()
