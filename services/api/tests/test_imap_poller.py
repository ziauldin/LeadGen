from email.message import EmailMessage as Mime

from sqlalchemy import select

from app.models.inbound import InboxCursor
from app.models.provider_credential import ProviderCredential
from app.models.reply import Reply
from app.services.inbound.imap_poller import poll_credential
from tests.conftest import TestingSessionLocal, auth_headers, get_client


def _raw(uid: int, *, subject="Re: hello", body="Interested, let's talk") -> bytes:
    msg = Mime()
    msg["From"] = f"person{uid}@client.example"
    msg["To"] = "sam@acme.example"
    msg["Subject"] = subject
    msg["Message-ID"] = f"<imap-{uid}@client.example>"
    msg.set_content(body)
    return msg.as_bytes()


class FakeImap:
    def __init__(self, messages: dict[int, bytes], uidvalidity: int = 1):
        self.messages = messages
        self.uidvalidity = uidvalidity
        self.logged_out = False

    def login(self, user, password):
        return "OK", [b"logged in"]

    def select(self, folder, readonly=True):
        return "OK", [str(len(self.messages)).encode()]

    def response(self, code):
        return code, [str(self.uidvalidity).encode()]

    def uid(self, command, *args):
        if command == "search":
            start = int(args[1].split()[1].split(":")[0])
            uids = [str(u).encode() for u in sorted(self.messages) if u >= start]
            return "OK", [b" ".join(uids)]
        uid = int(args[0])
        return "OK", [(f"{uid} (RFC822 {{}})".encode(), self.messages[uid]), b")"]

    def logout(self):
        self.logged_out = True


def _credential(client, headers) -> int:
    response = client.post(
        "/provider-settings",
        headers=headers,
        json={
            "provider_type": "inbox",
            "provider_name": "imap",
            "config": {"host": "imap.example", "username": "sam", "password": "pw"},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_poll_processes_new_messages_and_advances_cursor():
    client = get_client()
    headers = auth_headers(client)
    credential_id = _credential(client, headers)
    fake = FakeImap({101: _raw(101), 102: _raw(102)})

    db = TestingSessionLocal()
    db.info["tenant_bypass"] = True
    try:
        credential = db.get(ProviderCredential, credential_id)
        assert poll_credential(db, credential, factory=lambda _cfg: fake) == 2
        cursor = db.scalar(select(InboxCursor))
        assert cursor.last_uid == 102
        assert fake.logged_out
        # Nothing new: nothing processed again.
        assert poll_credential(db, credential, factory=lambda _cfg: fake) == 0

        # New message arrives.
        fake.messages[103] = _raw(103)
        assert poll_credential(db, credential, factory=lambda _cfg: fake) == 1
        assert len(db.scalars(select(Reply)).all()) == 3
    finally:
        db.close()


def test_uidvalidity_change_resets_the_cursor():
    client = get_client()
    headers = auth_headers(client)
    credential_id = _credential(client, headers)
    db = TestingSessionLocal()
    db.info["tenant_bypass"] = True
    try:
        credential = db.get(ProviderCredential, credential_id)
        poll_credential(
            db, credential, factory=lambda _cfg: FakeImap({500: _raw(500)}, uidvalidity=1)
        )
        assert db.scalar(select(InboxCursor)).last_uid == 500
        rebuilt = FakeImap({1: _raw(1)}, uidvalidity=2)
        assert poll_credential(db, credential, factory=lambda _cfg: rebuilt) == 1
        cursor = db.scalar(select(InboxCursor))
        assert (cursor.uidvalidity, cursor.last_uid) == (2, 1)
    finally:
        db.close()


def test_connection_errors_are_recorded_not_raised():
    client = get_client()
    headers = auth_headers(client)
    credential_id = _credential(client, headers)

    class Broken(FakeImap):
        def login(self, user, password):
            raise OSError("connection refused")

    db = TestingSessionLocal()
    db.info["tenant_bypass"] = True
    try:
        credential = db.get(ProviderCredential, credential_id)
        assert poll_credential(db, credential, factory=lambda _cfg: Broken({})) == 0
        assert "connection refused" in db.scalar(select(InboxCursor)).last_error
    finally:
        db.close()
