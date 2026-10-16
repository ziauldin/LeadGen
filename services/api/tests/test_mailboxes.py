import base64
import json
from datetime import UTC, datetime, timedelta
from email import message_from_bytes
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus
from app.models.provider_credential import ProviderCredential
from app.models.reply import Reply
from app.services.mailboxes import clients, oauth
from app.services.mailboxes import service as mailboxes
from tests.conftest import TestingSessionLocal, get_client
from tests.sending_helpers import approved_message


class FakeProviders:
    """Google OAuth + Gmail API and Microsoft identity + Graph, in one mock transport."""

    def __init__(self):
        self.sent: list[dict] = []
        self.token_requests: list[dict] = []
        self.revoked = False
        self.history: list[str] = []  # Gmail message ids added since the cursor
        self.raw_messages: dict[str, bytes] = {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(("https://oauth2.googleapis.com/token", "https://login.microsoftonline.com")):
            form = parse_qs(request.content.decode())
            self.token_requests.append({k: v[0] for k, v in form.items()})
            if self.revoked:
                return httpx.Response(400, json={"error": "invalid_grant", "error_description": "Token revoked"})
            return httpx.Response(
                200,
                json={"access_token": f"at-{len(self.token_requests)}", "refresh_token": "rt-1", "expires_in": 3600},
            )
        if url.endswith("/gmail/v1/users/me/profile"):
            return httpx.Response(200, json={"emailAddress": "Sam@Acme-Mail.co.uk", "historyId": "100"})
        if url.endswith("/gmail/v1/users/me/messages/send"):
            raw = base64.urlsafe_b64decode(json.loads(request.content)["raw"])
            self.sent.append({"provider": "gmail", "raw": raw, "auth": request.headers["Authorization"]})
            return httpx.Response(200, json={"id": f"gm-{len(self.sent)}"})
        if "/gmail/v1/users/me/history" in url:
            ids, self.history = self.history, []
            return httpx.Response(200, json={"historyId": "101", "history": [{"messagesAdded": [{"message": {"id": i}} for i in ids]}]})
        if "/gmail/v1/users/me/messages/" in url:
            message_id = urlparse(url).path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={"raw": base64.urlsafe_b64encode(self.raw_messages[message_id]).decode()})
        if url == "https://graph.microsoft.com/v1.0/me":
            return httpx.Response(200, json={"mail": "jo@contoso-mail.co.uk"})
        if url.endswith("/me/sendMail"):
            self.sent.append({"provider": "outlook", "raw": base64.b64decode(request.content), "auth": request.headers["Authorization"]})
            return httpx.Response(202)
        return httpx.Response(404, json={"error": {"message": f"unexpected {url}"}})


@pytest.fixture
def providers(monkeypatch):
    fake = FakeProviders()
    monkeypatch.setattr(settings, "feature_mailbox_oauth", True)
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "google-secret")
    monkeypatch.setattr(settings, "microsoft_oauth_client_id", "ms-client")
    monkeypatch.setattr(settings, "microsoft_oauth_client_secret", "ms-secret")
    monkeypatch.setattr(oauth, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(fake.handler)))
    return fake


def _connect(client, headers, provider="gmail"):
    started = client.post(f"/mailboxes/{provider}/connect", headers=headers)
    assert started.status_code == 200, started.text
    query = parse_qs(urlparse(started.json()["url"]).query)
    callback = client.get(
        f"/mailboxes/oauth/{provider}/callback",
        params={"code": "auth-code", "state": query["state"][0]},
        follow_redirects=False,
    )
    assert callback.status_code == 302
    return query, callback.headers["location"]


def _credential(provider="gmail"):
    db = TestingSessionLocal()
    try:
        return db.scalar(select(ProviderCredential).where(ProviderCredential.provider_name == provider))
    finally:
        db.close()


def test_flag_and_provider_list():
    client = get_client()
    from tests.conftest import auth_headers

    headers = auth_headers(client)
    assert client.post("/mailboxes/gmail/connect", headers=headers).status_code == 404
    assert all(not p["available"] for p in client.get("/mailboxes/providers", headers=headers).json())


def test_connect_gmail_with_pkce(providers):
    client = get_client()
    headers, _campaign, _ids = approved_message(client)
    query, location = _connect(client, headers)
    assert query["code_challenge_method"] == ["S256"]
    assert query["access_type"] == ["offline"]
    assert "gmail.send" in query["scope"][0]
    assert location.endswith("/settings/providers?mailbox=connected")
    # The PKCE verifier went to the token endpoint, and matches the challenge.
    verifier = providers.token_requests[0]["code_verifier"]
    import hashlib

    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == query["code_challenge"][0]

    credential = _credential()
    config = clients.config_of(credential)
    assert config["from_email"] == "sam@acme-mail.co.uk"
    assert config["refresh_token"] == "rt-1"
    assert credential.daily_limit == mailboxes.DEFAULT_MAILBOX_DAILY_LIMIT
    assert credential.warmup_enabled is True
    accounts = client.get("/sending-accounts", headers=headers).json()
    assert any(a["is_mailbox"] and a["email"] == "sam@acme-mail.co.uk" for a in accounts)

    # Tampered or cancelled callbacks land back in the app with an error.
    bad = client.get("/mailboxes/oauth/gmail/callback", params={"code": "x", "state": "nope"}, follow_redirects=False)
    assert "mailbox=error" in bad.headers["location"]
    cancelled = client.get("/mailboxes/oauth/gmail/callback", params={"error": "access_denied"}, follow_redirects=False)
    assert "mailbox=cancelled" in cancelled.headers["location"]
    wrong_provider = client.get(
        "/mailboxes/oauth/outlook/callback", params={"code": "x", "state": query["state"][0]}, follow_redirects=False
    )
    assert "mailbox=error" in wrong_provider.headers["location"]


def test_send_through_the_campaign_pool(providers):
    client = get_client()
    headers, campaign_id, message_ids = approved_message(client)
    _connect(client, headers)
    credential = _credential()
    pool = client.put(f"/campaigns/{campaign_id}/senders", headers=headers, json={"credential_ids": [credential.id]})
    assert pool.status_code == 200
    assert [a["id"] for a in client.get(f"/campaigns/{campaign_id}/senders", headers=headers).json()] == [credential.id]

    assert client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers).json()["sent"] == 1
    sent = providers.sent[0]
    mime = message_from_bytes(sent["raw"])
    assert mime["From"].endswith("<sam@acme-mail.co.uk>") or "sam@acme-mail.co.uk" in mime["From"]
    assert mime["To"] == "alex@example-foods.co.uk"
    assert mime["Message-ID"].startswith("<")
    db = TestingSessionLocal()
    try:
        message = db.get(EmailMessage, message_ids[0])
        assert message.sender_credential_id == credential.id
        assert message.provider_message_id == "gm-1"
    finally:
        db.close()


def test_outlook_sends_mime_through_graph(providers):
    client = get_client()
    headers, campaign_id, _ids = approved_message(client)
    _connect(client, headers, "outlook")
    credential = _credential("outlook")
    client.put(f"/campaigns/{campaign_id}/senders", headers=headers, json={"credential_ids": [credential.id]})
    assert client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers).json()["sent"] == 1
    assert providers.sent[0]["provider"] == "outlook"
    assert message_from_bytes(providers.sent[0]["raw"])["To"] == "alex@example-foods.co.uk"


def test_rotation_spreads_load_and_keeps_threads(providers):
    client = get_client()
    headers, campaign_id, message_ids = approved_message(
        client, emails=("a@example-foods.co.uk", "b@example-foods.co.uk")
    )
    _connect(client, headers, "gmail")
    _connect(client, headers, "outlook")
    gmail, outlook = _credential("gmail"), _credential("outlook")
    db = TestingSessionLocal()
    try:
        for row in (db.get(ProviderCredential, gmail.id), db.get(ProviderCredential, outlook.id)):
            row.daily_limit = 1
            row.warmup_enabled = False
        db.commit()
    finally:
        db.close()
    client.put(f"/campaigns/{campaign_id}/senders", headers=headers, json={"credential_ids": [gmail.id, outlook.id]})
    assert client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers).json()["sent"] == 2
    assert sorted(s["provider"] for s in providers.sent) == ["gmail", "outlook"]

    # A follow-up in the same enrollment reuses the mailbox that sent the first email.
    db = TestingSessionLocal()
    try:
        first = db.get(EmailMessage, message_ids[0])
        follow_up = EmailMessage(
            workspace_id=first.workspace_id,
            lead_id=first.lead_id,
            campaign_id=first.campaign_id,
            enrollment_id=first.enrollment_id,
            step_number=2,
            recipient_email=first.recipient_email,
            subject="Re: " + first.subject,
            body="Following up",
            status=EmailMessageStatus.APPROVED,
        )
        db.add(follow_up)
        db.flush()
        campaign = first.campaign
        chosen = mailboxes.choose_credential(db, campaign, follow_up, datetime.now(UTC))
        assert chosen.id == first.sender_credential_id
        db.rollback()
    finally:
        db.close()


def test_expired_tokens_refresh_and_revoked_ones_pause_the_mailbox(providers):
    client = get_client()
    headers, campaign_id, _ids = approved_message(client)
    _connect(client, headers)
    credential = _credential()
    db = TestingSessionLocal()
    try:
        row = db.get(ProviderCredential, credential.id)
        config = clients.config_of(row)
        config["expires_at"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
        clients.save_config(row, config)
        db.commit()
        clients.client_for(row)  # refreshes
        assert clients.config_of(row)["access_token"] == "at-2"
        assert providers.token_requests[-1]["grant_type"] == "refresh_token"

        config = clients.config_of(row)
        config["expires_at"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
        clients.save_config(row, config)
        db.commit()
    finally:
        db.close()

    providers.revoked = True
    client.put(f"/campaigns/{campaign_id}/senders", headers=headers, json={"credential_ids": [credential.id]})
    client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers)
    paused = _credential()
    assert paused.disabled_at is not None
    assert paused.disabled_reason.startswith("Reconnect needed")
    account = next(a for a in client.get("/sending-accounts", headers=headers).json() if a["id"] == credential.id)
    assert account["healthy"] is False


def test_gmail_replies_are_synced(providers):
    client = get_client()
    headers, campaign_id, message_ids = approved_message(client)
    _connect(client, headers)
    credential = _credential()
    client.put(f"/campaigns/{campaign_id}/senders", headers=headers, json={"credential_ids": [credential.id]})
    client.post(f"/campaigns/{campaign_id}/process-sends", headers=headers)
    db = TestingSessionLocal()
    try:
        sent = db.get(EmailMessage, message_ids[0])
        rfc_id = sent.rfc_message_id
        workspace_id = sent.workspace_id
    finally:
        db.close()

    from app.workers.inbound_jobs import sync_mailboxes

    db = TestingSessionLocal()
    try:
        assert sync_mailboxes(db) == 0  # first sync just records where to start
        providers.raw_messages["m1"] = (
            f"From: alex@example-foods.co.uk\r\nTo: sam@acme-mail.co.uk\r\nSubject: Re: hello\r\n"
            f"Message-ID: <reply-1@example-foods.co.uk>\r\nIn-Reply-To: <{rfc_id}>\r\n\r\n"
            "Yes, I'd like to hear more. Call me on Tuesday.\r\n"
        ).encode()
        providers.history = ["m1"]
        assert sync_mailboxes(db) == 1
        reply = db.scalar(select(Reply).where(Reply.workspace_id == workspace_id))
        assert reply.email_message_id == message_ids[0]
        assert clients.config_of(db.get(ProviderCredential, credential.id))["sync_cursor"] == "101"
    finally:
        db.close()


def test_health_pauses_bouncing_mailboxes_and_limits_apply(providers):
    client = get_client()
    headers, _campaign_id, message_ids = approved_message(client)
    _connect(client, headers)
    credential = _credential()
    db = TestingSessionLocal()
    try:
        template = db.get(EmailMessage, message_ids[0])
        for index in range(mailboxes.HEALTH_MIN_SENDS):
            db.add(
                EmailMessage(
                    workspace_id=template.workspace_id,
                    lead_id=template.lead_id,
                    campaign_id=template.campaign_id,
                    recipient_email=f"x{index}@example-foods.co.uk",
                    subject="s",
                    body="b",
                    step_number=1,
                    status=EmailMessageStatus.BOUNCED if index < 3 else EmailMessageStatus.SENT,
                    sender_credential_id=credential.id,
                    sent_at=datetime.now(UTC) - timedelta(days=2),
                )
            )
        db.commit()
        row = db.get(ProviderCredential, credential.id)
        assert mailboxes.check_health(db, row) is not None
        db.commit()
    finally:
        db.close()
    account = next(a for a in client.get("/sending-accounts", headers=headers).json() if a["id"] == credential.id)
    assert account["healthy"] is False and "bounces" in account["problem"]

    resumed = client.patch(f"/sending-accounts/{credential.id}", headers=headers, json={"resume": True, "daily_limit": 1})
    assert resumed.json()["healthy"] is True
    assert resumed.json()["daily_limit"] == 1
