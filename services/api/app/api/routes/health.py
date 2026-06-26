from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.database import get_db
from app.schemas.health import DependencyStatus, HealthReadyResponse
from app.services.health.checks import check_database, check_redis

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": app_settings.environment}


@router.get("/health/ready", response_model=HealthReadyResponse)
def readiness_check(response: Response, db: Session = Depends(get_db)) -> HealthReadyResponse:
    db_ok, db_error = check_database(db)
    redis_ok, redis_error = check_redis()

    dependencies = [
        DependencyStatus(name="database", status="ok" if db_ok else "error", detail=db_error),
        DependencyStatus(name="redis", status="ok" if redis_ok else "error", detail=redis_error),
    ]

    ready = db_ok and redis_ok
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthReadyResponse(
        status="ready" if ready else "degraded",
        environment=app_settings.environment,
        dependencies=dependencies,
    )
