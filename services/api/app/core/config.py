from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "LeadsGen"
    environment: str = "development"

    database_url: str = DEFAULT_SQLITE_URL
    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = "change-me-to-a-long-random-string"
    secret_encryption_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440

    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    search_provider: str = "mock"
    email_provider: str = "mock"

    google_cse_api_key: str = ""
    google_cse_cx: str = ""
    bing_search_api_key: str = ""
    serpapi_api_key: str = ""

    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""

    default_daily_send_limit: int = 20
    default_per_domain_limit: int = 3
    default_sending_window_start: str = "09:00"
    default_sending_window_end: str = "17:00"

    enrichment_user_agent: str = "LeadsGenBot/0.1 (B2B enrichment; respects robots.txt)"
    enrichment_request_timeout: int = 10
    enrichment_rate_limit_seconds: float = 1.0
    enrichment_max_pages: int = 3

    api_public_url: str = "http://localhost:8000"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
