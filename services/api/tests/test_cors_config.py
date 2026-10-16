from app.core.config import Settings, normalize_cors_origin


def test_normalize_cors_origin_adds_https_and_strips_slash() -> None:
    assert (
        normalize_cors_origin("leadgen-production-31e7.up.railway.app")
        == "https://leadgen-production-31e7.up.railway.app"
    )
    assert normalize_cors_origin("https://example.com/") == "https://example.com"


def test_production_has_no_wildcard_origin_regex() -> None:
    settings = Settings(
        environment="production",
        secret_encryption_key="test-key",
        cors_origins=["https://leadgen-production-31e7.up.railway.app"],
    )
    # Allowing every *.up.railway.app origin would let other people's apps call the API.
    assert settings.resolved_cors_origin_regex() is None


def test_explicit_origin_regex_is_honoured() -> None:
    pattern = r"https://preview-[0-9]+[.]leadsgen[.]app"
    settings = Settings(
        environment="production", secret_encryption_key="k", cors_origin_regex=pattern
    )
    assert settings.resolved_cors_origin_regex() == pattern


def test_development_has_no_origin_regex_by_default() -> None:
    settings = Settings(environment="development", secret_encryption_key="test-key")
    assert settings.resolved_cors_origin_regex() is None
