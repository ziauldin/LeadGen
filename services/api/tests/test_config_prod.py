from cryptography.fernet import Fernet

from app.core import security
from app.core.config import PLACEHOLDER_SECRET_KEY, Settings, production_config_errors, settings

GOOD = {
    "environment": "production",
    "secret_key": "s" * 48,
    "secret_encryption_key": "k",
    "database_url": "postgresql://u:p@db:5432/app",
    "api_public_url": "https://api.leadsgen.app",
    "frontend_url": "https://app.leadsgen.app",
    "cors_origins": ["https://app.leadsgen.app"],
    "platform_email_provider": "resend",
}


def test_valid_production_config_has_no_errors():
    assert production_config_errors(Settings(**GOOD)) == []


def test_placeholder_secret_key_is_rejected():
    errors = production_config_errors(Settings(**{**GOOD, "secret_key": PLACEHOLDER_SECRET_KEY}))
    assert any("SECRET_KEY" in e for e in errors)


def test_sqlite_and_http_urls_are_rejected():
    errors = production_config_errors(
        Settings(
            **{
                **GOOD,
                "database_url": "sqlite:///x.db",
                "api_public_url": "http://api",
                "cors_origins": ["http://app"],
            },
        ),
    )
    joined = " ".join(errors)
    assert "PostgreSQL" in joined
    assert "API_PUBLIC_URL" in joined
    assert "CORS_ORIGINS" in joined


def test_wildcard_hosting_regex_is_rejected():
    regex = "https://[a-z0-9-]+[.]up.railway.app"
    errors = production_config_errors(Settings(**{**GOOD, "cors_origin_regex": regex}))
    assert any("CORS_ORIGIN_REGEX" in e for e in errors)


def test_missing_encryption_key_is_rejected():
    errors = production_config_errors(Settings(**{**GOOD, "secret_encryption_key": ""}))
    assert any("ENCRYPTION" in e for e in errors)


def test_postgres_scheme_is_normalised():
    assert Settings(database_url="postgres://u:p@h/db").database_url.startswith("postgresql://")


def test_key_rotation_decrypts_old_ciphertext(monkeypatch):
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "secret_encryption_keys", "")
    monkeypatch.setattr(settings, "secret_encryption_key", old_key)
    token = security.encrypt_secret_payload("hello")

    monkeypatch.setattr(settings, "secret_encryption_keys", f"{new_key},{old_key}")
    assert security.decrypt_secret_payload(token) == "hello"
