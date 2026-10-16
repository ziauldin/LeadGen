from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def normalize_cors_origin(origin: str) -> str:
    """Normalize a CORS origin (scheme, no trailing slash)."""
    normalized = origin.strip()
    if not normalized:
        return normalized
    if not normalized.startswith(("http://", "https://")):
        normalized = f"https://{normalized}"
    return normalized.rstrip("/")


def _find_env_file() -> Path | None:
    """Load .env from repo root or services/api directory."""
    here = Path(__file__).resolve()
    candidates: list[Path] = [here.parents[2] / ".env"]  # services/api/.env
    # Monorepo local dev only — Railway deploys services/api alone (no parents[4]).
    if len(here.parents) > 4:
        candidates.insert(0, here.parents[4] / ".env")
    for path in candidates:
        if path.is_file():
            return path
    return None


ENV_FILE = _find_env_file()

_API_ROOT = Path(__file__).resolve().parents[2]
_SQLITE_DB_PATH = _API_ROOT / "data" / "leadsgen.db"
_SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DEFAULT_SQLITE_URL = f"sqlite:///{_SQLITE_DB_PATH.resolve().as_posix()}"


PLACEHOLDER_SECRET_KEY = "change-me-to-a-long-random-string"  # noqa: S105 - rejected in production


def normalize_database_url(url: str) -> str:
    """Pin PostgreSQL URLs to the psycopg 3 driver.

    Railway/Heroku hand out ``postgres://`` or driver-less ``postgresql://`` URLs; SQLAlchemy's
    default driver for those differs between versions, so name the one we install.
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "LeadsGen"
    environment: str = "development"
    log_level: str = "INFO"
    log_json: bool | None = None  # defaults to JSON logs outside development/test

    database_url: str = DEFAULT_SQLITE_URL
    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = PLACEHOLDER_SECRET_KEY
    # Primary Fernet key. SECRET_ENCRYPTION_KEYS (comma-separated, newest first) enables rotation.
    secret_encryption_key: str = ""
    secret_encryption_keys: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30

    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    cors_origin_regex: str | None = None

    # Refresh-token cookie. The default path assumes the web app proxies the API under /api.
    refresh_cookie_name: str = "lg_refresh"
    refresh_cookie_path: str = "/api/auth"
    refresh_cookie_secure: bool | None = None  # defaults to True outside development/test
    refresh_cookie_samesite: str = "lax"  # use "none" only for a cross-site API without proxy
    refresh_cookie_domain: str | None = None
    require_email_verification: bool = True

    # Rate limiting (slowapi). Use Redis in production so limits hold across instances.
    rate_limit_enabled: bool = True
    rate_limit_storage_url: str | None = None  # defaults to REDIS_URL outside dev/test
    rate_limit_default: str = "600/minute"
    trusted_proxy_hops: int = 1

    # Celery: run tasks inline (tests / e2e only).
    celery_task_always_eager: bool = False

    # Platform transactional email (verify / reset / invite). Never used for outreach.
    platform_email_provider: str = "console"  # console | resend | smtp
    platform_email_from: str = "LeadsGen <no-reply@localhost>"
    platform_email_api_key: str = ""
    platform_smtp_host: str = ""
    platform_smtp_port: int = 587
    platform_smtp_username: str = ""
    platform_smtp_password: str = ""
    # Off only for a local catch-all server such as Mailpit; required in production.
    platform_smtp_use_tls: bool = True

    # Domain whose MX routes to our inbound webhook/IMAP (reply+token@, unsubscribe+token@).
    inbound_email_domain: str = ""

    frontend_url: str = "http://localhost:3000"
    api_public_url: str = "http://localhost:8000"
    expose_api_docs: bool = True

    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.0
    railway_git_commit_sha: str = ""

    # Dark-launch flags for the new production features.
    feature_ai_emails: bool = False
    feature_imap: bool = False
    feature_inbound_webhooks: bool = False

    # Platform-paid LLM, used when a workspace has no key of its own: groq | openai | gemini |
    # mock | "" (off). Workspace keys are stored encrypted as "llm" provider credentials.
    platform_llm_provider: str = ""
    platform_llm_api_key: str = ""
    platform_llm_model: str = ""
    llm_timeout_seconds: float = 30.0

    email_discovery_provider: str = "none"
    hunter_api_key: str = ""
    hunter_daily_limit: int = 25
    hunter_enabled: bool = False

    default_daily_send_limit: int = 20
    default_per_domain_limit: int = 3
    default_sending_window_start: str = "09:00"
    default_sending_window_end: str = "17:00"

    enrichment_user_agent: str = "LeadsGenBot/0.1 (B2B enrichment; respects robots.txt)"
    enrichment_request_timeout: int = 10
    enrichment_rate_limit_seconds: float = 1.0
    enrichment_max_pages: int = 3
    enrichment_max_response_bytes: int = 2_000_000

    csv_max_bytes: int = 5_000_000
    csv_max_rows: int = 10_000

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            raw = [origin.strip() for origin in value.split(",") if origin.strip()]
        else:
            raw = value
        return [normalize_cors_origin(origin) for origin in raw if origin.strip()]

    @field_validator("database_url", mode="after")
    @classmethod
    def normalize_db_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_test_like(self) -> bool:
        return self.environment in {"test", "development"}

    @property
    def use_json_logs(self) -> bool:
        if self.log_json is not None:
            return self.log_json
        return self.environment not in {"development", "test"}

    @property
    def cookie_secure(self) -> bool:
        if self.refresh_cookie_secure is not None:
            return self.refresh_cookie_secure
        return self.environment not in {"development", "test"}

    @property
    def resolved_rate_limit_storage(self) -> str:
        if self.rate_limit_storage_url:
            return self.rate_limit_storage_url
        return "memory://" if self.environment in {"development", "test"} else self.redis_url

    def encryption_keys(self) -> list[str]:
        keys = [key.strip() for key in self.secret_encryption_keys.split(",") if key.strip()]
        if self.secret_encryption_key and self.secret_encryption_key not in keys:
            keys.append(self.secret_encryption_key)
        return keys

    def resolved_cors_origin_regex(self) -> str | None:
        # Only an explicit regex is honoured. Wildcard hosting domains (any *.up.railway.app or
        # *.vercel.app) would let other tenants' apps call the API with credentials.
        return self.cors_origin_regex or None


def production_config_errors(config: Settings) -> list[str]:
    """Configuration problems that must stop the API from starting in production."""
    errors: list[str] = []
    if len(config.secret_key) < 32 or config.secret_key == PLACEHOLDER_SECRET_KEY:
        errors.append("SECRET_KEY must be a random string of at least 32 characters")
    if not config.encryption_keys():
        errors.append("SECRET_ENCRYPTION_KEY (or SECRET_ENCRYPTION_KEYS) must be set")
    if not config.database_url.startswith("postgresql"):
        errors.append("DATABASE_URL must point at PostgreSQL in production")
    for name in ("api_public_url", "frontend_url"):
        if not getattr(config, name).startswith("https://"):
            errors.append(f"{name.upper()} must be an https:// URL in production")
    if not config.cors_origins or any(o.startswith("http://") for o in config.cors_origins):
        errors.append("CORS_ORIGINS must list the https frontend origin(s) explicitly")
    if config.platform_email_provider == "console":
        errors.append("PLATFORM_EMAIL_PROVIDER must be resend or smtp in production")
    if config.platform_email_provider == "smtp" and not config.platform_smtp_use_tls:
        errors.append("PLATFORM_SMTP_USE_TLS must be on in production")
    if config.platform_llm_provider == "mock":
        errors.append("PLATFORM_LLM_PROVIDER must not be mock in production")
    if config.celery_task_always_eager:
        errors.append("CELERY_TASK_ALWAYS_EAGER must not be enabled in production")
    if config.cors_origin_regex and any(
        host in config.cors_origin_regex.lower() for host in ("railway", "vercel")
    ):
        errors.append("CORS_ORIGIN_REGEX must not allow every Railway/Vercel subdomain")
    return errors


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
