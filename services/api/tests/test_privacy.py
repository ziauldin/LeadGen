import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import pytest
from sqlalchemy import select

from app.core.storage import LocalStorage
from app.models.audit_log import AuditLog
from app.models.email_contact import EmailContact
from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus
from app.models.lead import Lead
from app.models.privacy import DataRequest
from app.models.reply import Reply
from app.models.suppression import Suppression
from app.models.user import User
from app.models.workspace import Workspace
from app.services.compliance.outreach import is_email_suppressed, validate_lead_for_outreach
from app.services.privacy.service import apply_retention, email_hash, purge_expired_exports
from tests.conftest import TestingSessionLocal, auth_headers, get_client
from tests.sending_helpers import approved_message

ALEX = "alex@example-foods.co.uk"
BLAIR = "blair@example-foods.co.uk"


@pytest.fixture
def store(tmp_path, monkeypatch):
    local = LocalStorage(tmp_path)
    for target in (
        "app.services.privacy.service.get_storage",
        "app.api.routes.privacy.get_storage",
        "app.api.routes.health.get_storage",
    ):
        monkeypatch.setattr(target, lambda: local)
    return local


def _download(client, headers, request_id) -> zipfile.ZipFile:
    response = client.post(f"/privacy/requests/{request_id}/download", headers=headers)
    assert response.status_code == 200, response.text
    url = urlparse(response.json()["url"])
    file = client.get(f"{url.path}?{url.query}")
    assert file.status_code == 200
    return zipfile.ZipFile(io.BytesIO(file.content))


def _mark_sent_with_reply(message_id, email):
    db = TestingSessionLocal()
    try:
        message = db.get(EmailMessage, message_id)
        message.status = EmailMessageStatus.SENT
        message.sent_at = datetime.now(UTC)
        db.add(
            Reply(
                workspace_id=message.workspace_id,
                email_message_id=message.id,
                lead_id=message.lead_id,
                from_email=email,
                body="Sounds interesting, tell me more",
                received_at=datetime.now(UTC),
            )
        )
        db.commit()
    finally:
        db.close()


def test_lawful_basis_defaults_and_optional_lia_requirement():
    client = get_client()
    headers, _campaign, _message_ids = approved_message(client)
    lead = client.get("/leads", headers=headers).json()["items"][0]
    assert lead["lawful_basis"] == "legitimate_interest"
    assert lead["lawful_basis_note"] is None

    db = TestingSessionLocal()
    try:
        model = db.get(Lead, lead["id"])
        assert validate_lead_for_outreach(model, db) == []
    finally:
        db.close()

    assert (
        client.put(
            "/privacy/settings", headers=headers, json={"require_lia_note": True}
        ).status_code
        == 200
    )
    db = TestingSessionLocal()
    try:
        assert (
            "Lead needs a legitimate-interest note before outreach"
            in validate_lead_for_outreach(db.get(Lead, lead["id"]), db)
        )
    finally:
        db.close()

    note = "Supplier to food manufacturers; role matches our quality software."
    updated = client.patch(
        f"/leads/{lead['id']}", headers=headers, json={"lawful_basis_note": note}
    )
    assert updated.json()["lawful_basis_note"] == note
    # A basis can be changed but never removed.
    assert (
        client.patch(f"/leads/{lead['id']}", headers=headers, json={"lawful_basis": None}).json()[
            "lawful_basis"
        ]
        == "legitimate_interest"
    )
    assert (
        client.patch(
            f"/leads/{lead['id']}", headers=headers, json={"lawful_basis": "nope"}
        ).status_code
        == 422
    )
    db = TestingSessionLocal()
    try:
        assert validate_lead_for_outreach(db.get(Lead, lead["id"]), db) == []
    finally:
        db.close()


def test_export_one_person(store):
    client = get_client()
    headers, _campaign, _message_ids = approved_message(client, emails=(ALEX, BLAIR))
    created = client.post(
        "/privacy/requests",
        headers=headers,
        json={"kind": "export", "email": " Alex@Example-Foods.co.uk "},
    )
    assert created.status_code == 201, created.text
    request = created.json()
    assert request["status"] == "completed"
    assert request["downloadable"] is True
    assert request["subject_email"] == ALEX
    assert request["summary"]["contacts"] == 1

    archive = _download(client, headers, request["id"])
    assert set(archive.namelist()) == {"README.txt", "person.json"}
    person = json.loads(archive.read("person.json"))
    assert [c["email"] for c in person["contacts"]] == [ALEX]
    assert len(person["leads"]) == 1
    assert person["leads"][0]["lawful_basis"] == "legitimate_interest"
    assert all(m["recipient_email"] == ALEX for m in person["messages"])
    assert BLAIR not in archive.read("person.json").decode()


def test_erase_one_person_keeps_only_a_hash(store):
    client = get_client()
    headers, _campaign, message_ids = approved_message(client, emails=(ALEX, BLAIR))
    alex_message = next(
        m for m in message_ids if TestingSessionLocal().get(EmailMessage, m).recipient_email == ALEX
    )
    _mark_sent_with_reply(alex_message, ALEX)
    export = client.post(
        "/privacy/requests", headers=headers, json={"kind": "export", "email": ALEX}
    ).json()
    export_key = TestingSessionLocal().get(DataRequest, export["id"]).file_key

    erase = client.post(
        "/privacy/requests",
        headers=headers,
        json={"kind": "erase", "email": ALEX, "note": "Email from Alex, 3 Oct"},
    )
    assert erase.status_code == 201, erase.text
    body = erase.json()
    assert body["status"] == "completed"
    assert body["subject_email"] is None
    assert body["summary"]["leads"] == 1
    assert body["summary"]["replies"] == 1

    db = TestingSessionLocal()
    try:
        workspace_id = db.get(DataRequest, body["id"]).workspace_id
        assert db.scalars(select(EmailContact).where(EmailContact.email == ALEX)).all() == []
        assert (
            db.scalars(select(EmailMessage).where(EmailMessage.recipient_email == ALEX)).all() == []
        )
        assert db.scalars(select(Reply).where(Reply.from_email == ALEX)).all() == []
        assert db.scalars(select(Suppression).where(Suppression.email == ALEX)).all() == []
        hashed = db.scalar(select(Suppression).where(Suppression.email_hash == email_hash(ALEX)))
        assert hashed is not None and hashed.reason_code == "erasure"
        # They stay blocked, matched by hash.
        assert is_email_suppressed(db, workspace_id, ALEX.upper())
        # Blair is untouched.
        assert db.scalars(select(EmailContact).where(EmailContact.email == BLAIR)).all()
        # The earlier export is gone too.
        earlier = db.get(DataRequest, export["id"])
        assert earlier.subject_email is None and earlier.file_key is None
        assert not store.path_for(export_key).exists()
        # Nothing in the audit log names the person.
        for log in db.scalars(select(AuditLog).where(AuditLog.workspace_id == workspace_id)).all():
            assert ALEX not in json.dumps(log.metadata_ or {})
    finally:
        db.close()

    listing = client.get("/privacy/requests", headers=headers).json()
    assert listing["total"] == 2
    assert all(item["subject_email"] is None for item in listing["items"])


def test_workspace_export_and_member_permissions(store):
    client = get_client()
    headers, _campaign, _ids = approved_message(client)
    db = TestingSessionLocal()
    try:
        owner = db.scalar(select(User).where(User.email == "test@example.com"))
        workspace = db.get(Workspace, owner.last_workspace_id)
        workspace.plan = "pro"
        db.commit()
    finally:
        db.close()
    from app.services.platform_email.mailer import OUTBOX

    client.post(
        "/workspaces/current/invitations",
        headers=headers,
        json={"email": "m@example.com", "role": "member"},
    )
    token = next(
        m.text.split("/invite/")[1].split()[0] for m in reversed(OUTBOX) if m.to == "m@example.com"
    )
    member = auth_headers(client, "m@example.com")
    workspace_id = client.post(f"/invitations/{token}/accept", headers=member).json()["id"]
    member = {**member, "X-Workspace-Id": str(workspace_id)}

    # Members can't export or erase a person, or change retention.
    assert (
        client.post(
            "/privacy/requests", headers=member, json={"kind": "erase", "email": ALEX}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/privacy/requests", headers=member, json={"kind": "export", "email": ALEX}
        ).status_code
        == 403
    )
    assert (
        client.put("/privacy/settings", headers=member, json={"require_lia_note": True}).status_code
        == 403
    )
    # They can export the workspace (data.export) and only see their own exports.
    client.post("/privacy/requests", headers=headers, json={"kind": "export", "email": ALEX})
    mine = client.post("/privacy/requests", headers=member, json={"kind": "workspace_export"})
    assert mine.status_code == 201, mine.text
    listing = client.get("/privacy/requests", headers=member).json()
    assert [item["id"] for item in listing["items"]] == [mine.json()["id"]]

    archive = _download(client, member, mine.json()["id"])
    assert "leads.csv" in archive.namelist()
    assert "provider_credentials.csv" not in archive.namelist()
    assert ALEX in archive.read("email_contacts.csv").decode()
    assert mine.json()["summary"]["leads"] == 1


def test_expired_exports_are_removed(store):
    client = get_client()
    headers, _campaign, _ids = approved_message(client)
    request = client.post(
        "/privacy/requests", headers=headers, json={"kind": "workspace_export"}
    ).json()
    db = TestingSessionLocal()
    try:
        row = db.get(DataRequest, request["id"])
        key = row.file_key
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
        assert purge_expired_exports(db) == 1
        assert db.get(DataRequest, request["id"]).file_key is None
    finally:
        db.close()
    assert not store.path_for(key).exists()
    assert (
        client.post(f"/privacy/requests/{request['id']}/download", headers=headers).status_code
        == 404
    )


def test_retention_rules(store):
    client = get_client()
    headers, _campaign, message_ids = approved_message(client, emails=(ALEX, BLAIR))
    assert (
        client.put(
            "/privacy/settings", headers=headers, json={"retention_uncontacted_lead_days": 10}
        ).status_code
        == 422
    )
    saved = client.put(
        "/privacy/settings",
        headers=headers,
        json={"retention_uncontacted_lead_days": 180, "retention_reply_days": 365},
    )
    assert saved.status_code == 200
    assert client.get("/privacy/settings", headers=headers).json()["retention_reply_days"] == 365

    alex_message = next(
        m for m in message_ids if TestingSessionLocal().get(EmailMessage, m).recipient_email == ALEX
    )
    _mark_sent_with_reply(alex_message, ALEX)
    long_ago = datetime.now(UTC) - timedelta(days=400)
    db = TestingSessionLocal()
    try:
        for lead in db.scalars(select(Lead)).all():
            lead.created_at = long_ago
        for reply in db.scalars(select(Reply)).all():
            reply.received_at = long_ago
        db.commit()

        totals = apply_retention(db)
        assert totals["leads"] == 1  # Blair was never emailed; Alex was, so stays
        assert totals["replies"] == 1
        remaining = db.scalars(select(EmailContact.email)).all()
        assert remaining == [ALEX]
    finally:
        db.close()
