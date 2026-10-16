"""Start a throwaway API for the Playwright end-to-end tests.

Fresh SQLite database, background jobs run inline, account emails logged to e2e-api.log
(the tests read verification links from there). Never use outside local/CI testing.
"""

import os
import subprocess
import sys
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "e2e.db"
LOG = ROOT / "e2e-api.log"
PORT = os.environ.get("E2E_API_PORT", "8010")
WEB = os.environ.get("E2E_WEB_URL", "http://localhost:3100")

env = {
    **os.environ,
    "ENVIRONMENT": "development",
    "DATABASE_URL": f"sqlite:///{DB.as_posix()}",
    "CELERY_TASK_ALWAYS_EAGER": "true",
    "PLATFORM_EMAIL_PROVIDER": "console",
    "RATE_LIMIT_ENABLED": "false",
    "LOG_JSON": "false",
    "REFRESH_COOKIE_SECURE": "false",
    "API_PUBLIC_URL": f"http://localhost:{PORT}",
    "FRONTEND_URL": WEB,
    "CORS_ORIGINS": WEB,
    "SECRET_KEY": "e2e-secret-key-that-is-long-enough-for-signing-tokens",
    "SECRET_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "FEATURE_SSO": "true",
    # The admin journey grants a superuser from the CLI; it skips the 2FA requirement here.
    "SUPERUSER_REQUIRE_MFA": "false",
    "FEATURE_CRM": "true",
    "FEATURE_ANALYTICS_V2": "true",
    "FEATURE_INTEGRATIONS": "true",
    "FEATURE_PUBLIC_API": "true",
}


def main() -> None:
    DB.parent.mkdir(exist_ok=True)
    DB.unlink(missing_ok=True)
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True
    )
    with LOG.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(  # noqa: S603 - fixed arguments
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", PORT],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            sys.exit(process.wait())
        except KeyboardInterrupt:
            process.terminate()


if __name__ == "__main__":
    main()
