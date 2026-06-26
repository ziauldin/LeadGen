from app.core.config import Settings, normalize_cors_origin


def test_normalize_cors_origin_adds_https_and_strips_slash() -> None:
    assert (
        normalize_cors_origin("leadgen-production-31e7.up.railway.app")
        == "https://leadgen-production-31e7.up.railway.app"
    )
    assert normalize_cors_origin("https://example.com/") == "https://example.com"


def test_production_enables_hosted_origin_regex() -> None:
    settings = Settings(
        environment="production",
        secret_encryption_key="test-key",
        cors_origins=["https://leadgen-production-31e7.up.railway.app"],
    )
    regex = settings.resolved_cors_origin_regex()
    assert regex is not None
    assert "up\\.railway" in regex


def test_development_has_no_origin_regex_by_default() -> None:
    settings = Settings(environment="development", secret_encryption_key="test-key")
    assert settings.resolved_cors_origin_regex() is None
