import os
import re

from cryptography.fernet import Fernet

os.environ.setdefault("SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("REFRESH_COOKIE_PATH", "/auth")
os.environ.setdefault("FEATURE_INBOUND_WEBHOOKS", "true")
os.environ.setdefault("FEATURE_IMAP", "true")
os.environ.setdefault("FEATURE_AI_EMAILS", "true")
os.environ.setdefault("FEATURE_SSO", "true")
# Optional features start off in tests whatever a developer's local .env says; tests turn
# them on explicitly.
os.environ.setdefault("FEATURE_PUBLIC_API", "false")
os.environ.setdefault("FEATURE_BILLING", "false")
os.environ.setdefault("FEATURE_MAILBOX_OAUTH", "false")
os.environ.setdefault("FEATURE_CRM", "false")
os.environ.setdefault("FEATURE_ANALYTICS_V2", "false")
os.environ.setdefault("FEATURE_INTEGRATIONS", "false")
os.environ.setdefault("HUNTER_ENABLED", "false")
os.environ.setdefault("PLATFORM_VERIFICATION_PROVIDER", "")
os.environ.setdefault("PLATFORM_LLM_PROVIDER", "mock")
os.environ.setdefault("PASSWORD_BREACH_CHECK", "false")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-for-hs256-signing")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import database as core_database
from app.core.config import normalize_database_url
from app.core.database import Base, get_db
from app.core.rate_limit import reset_rate_limits
from app.main import app
from app.services.llm.mock import reset_mock_llm
from app.services.platform_email.mailer import OUTBOX

# Tests use in-memory SQLite by default. Set TEST_DATABASE_URL to run the same suite on a real
# PostgreSQL database (CI does), e.g. postgresql://postgres@localhost:5432/leadgen_test
SQLALCHEMY_DATABASE_URL = normalize_database_url(os.environ.get("TEST_DATABASE_URL") or "sqlite://")
IS_POSTGRES = SQLALCHEMY_DATABASE_URL.startswith("postgresql")

engine = (
    create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
    if IS_POSTGRES
    else create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
)
# Sessions the app uses for requests: strictly workspace-scoped, like production.
AppSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Sessions tests use to set up and inspect data: see every workspace (and bypass RLS).
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, info={"tenant_bypass": True}
)
# Background tasks run eagerly in tests and open sessions via SessionLocal: point it here too.
core_database.SessionLocal.configure(bind=engine)


def override_get_db():
    db = AppSessionLocal()
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
    if IS_POSTGRES:
        # Other tests (e.g. migrations) may leave a differently-built schema behind.
        engine.dispose()
        with engine.begin() as conn:
            conn.exec_driver_sql("DROP SCHEMA public CASCADE")
            conn.exec_driver_sql("CREATE SCHEMA public")
    else:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    if IS_POSTGRES:
        _apply_row_level_security()


def tenant_table_names() -> list[str]:
    """Every table whose model uses the TenantScoped mixin."""
    from app.models.workspace import TenantScoped

    return sorted(
        mapper.class_.__tablename__
        for mapper in Base.registry.mappers
        if issubclass(mapper.class_, TenantScoped)
    )


def _apply_row_level_security() -> None:
    """The same policies the migrations create, so the suite runs with them on PostgreSQL."""
    bypass = "current_setting('app.bypass_rls', true) = 'on'"
    own = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::integer"
    with engine.begin() as conn:
        for table in tenant_table_names():
            conn.exec_driver_sql(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            conn.exec_driver_sql(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            conn.exec_driver_sql(
                f"CREATE POLICY tenant_isolation ON {table} USING ({bypass} OR {own}) "
                f"WITH CHECK ({bypass} OR {own})",
            )
        conn.exec_driver_sql("ALTER TABLE suppressions ENABLE ROW LEVEL SECURITY")
        conn.exec_driver_sql("ALTER TABLE suppressions FORCE ROW LEVEL SECURITY")
        conn.exec_driver_sql(
            "CREATE POLICY tenant_isolation ON suppressions USING "
            f"({bypass} OR workspace_id IS NULL OR {own}) WITH CHECK "
            f"({bypass} OR workspace_id IS NULL OR {own})",
        )


def get_client() -> TestClient:
    setup_db()
    reset_rate_limits()
    OUTBOX.clear()
    reset_mock_llm()
    return TestClient(app)
