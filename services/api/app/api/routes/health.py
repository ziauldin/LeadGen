import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.database import get_db
from app.core.metrics import render_metrics
from app.schemas.health import DependencyStatus, HealthReadyResponse
from app.services.health.checks import (
    check_database,
    check_migrations,
    check_redis,
    check_worker_heartbeat,
)

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Liveness: the process is up. Used by the platform's health check."""
    return {"status": "ok", "environment": app_settings.environment}


@router.get("/metrics", include_in_schema=False)
def metrics(authorization: str | None = Header(default=None)) -> Response:
    """Prometheus metrics. Needs METRICS_TOKEN set and sent as a bearer token."""
    token = app_settings.metrics_token
    if not token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if not authorization or not hmac.compare_digest(authorization, f"Bearer {token}"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)


@router.get("/health/ready", response_model=HealthReadyResponse)
def readiness_check(response: Response, db: Session = Depends(get_db)) -> HealthReadyResponse:
    """Readiness.

    ``ready`` (200): everything is up. ``degraded`` (200): the API works but background
    workers aren't running, so emails won't send. ``not_ready`` (503): the database, Redis or
    migrations are broken.
    """
    db_ok, db_error = check_database(db)
    redis_ok, redis_error = check_redis()
    migrations_ok, migrations_error = check_migrations(db) if db_ok else (False, "Database down")
    worker_ok, worker_error = check_worker_heartbeat() if redis_ok else (False, "Redis down")

    def entry(name: str, ok: bool, detail: str | None, *, fail: str = "error") -> DependencyStatus:
        return DependencyStatus(name=name, status="ok" if ok else fail, detail=detail)

    dependencies = [
        entry("database", db_ok, db_error),
        entry("redis", redis_ok, redis_error),
        entry("migrations", migrations_ok, migrations_error),
        entry("worker", worker_ok, worker_error, fail="missing"),
    ]
    if not (db_ok and redis_ok and migrations_ok):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        overall = "not_ready"
    else:
        overall = "ready" if worker_ok else "degraded"
    return HealthReadyResponse(
        status=overall,
        environment=app_settings.environment,
        dependencies=dependencies,
    )
