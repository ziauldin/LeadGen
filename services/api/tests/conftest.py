import os
import re

from cryptography.fernet import Fernet

os.environ.setdefault("SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("REFRESH_COOKIE_PATH", "/auth")
os.environ.setdefault("FEATURE_INBOUND_WEBHOOKS", "true")
os.environ.setdefault("FEATURE_IMAP", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-for-hs256-signing")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import database as core_database
from app.core.database import Base, get_db
from app.core.rate_limit import reset_rate_limits
from app.main import app
from app.services.platform_email.mailer import OUTBOX

SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Background tasks run eagerly in tests and open sessions via SessionLocal: point it here too.
core_database.SessionLocal.configure(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

_TOKEN_RE = re.compile(r"token=([A-Za-z0-9_\-%]+)")


def latest_email_token(email: str, kind: str) -> str:
    """Token from the newest platform email of ``kind`` (verify/reset) sent to ``email``."""
    for message in reversed(OUTBOX):
        if message.to == email and message.tags.get("kind") == kind:
            match = _TOKEN_RE.search(message.text)
            if match:
                return match.group(1)
    raise AssertionError(f"No {kind} email found for {email}")


def register_user(
    client: TestClient,
    email: str = "test@example.com",
    password: str = "testpass12",
    name: str = "Test User",
    *,
    verify: bool = True,
) -> None:
    client.post("/auth/register", json={"name": name, "email": email, "password": password})
    if verify:
        token = latest_email_token(email, "verify")
        response = client.post("/auth/verify-email", json={"token": token})
        assert response.status_code == 200, response.text


def login(client: TestClient, email: str, password: str = "testpass12") -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def auth_headers(
    client: TestClient,
    email: str = "test@example.com",
    password: str = "testpass12",
    *,
    verify: bool = True,
) -> dict[str, str]:
    register_user(client, email, password, verify=verify)
    return login(client, email, password)


def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def get_client() -> TestClient:
    setup_db()
    reset_rate_limits()
    OUTBOX.clear()
    return TestClient(app)
