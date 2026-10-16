import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import (
    admin,
    approvals,
    auth,
    billing,
    campaigns,
    companies,
    compliance,
    crm,
    dashboard,
    developer,
    emails,
    health,
    inbox,
    leads,
    mailboxes,
    niches,
    notifications,
    privacy,
    provider_settings,
    public,
    replies,
    roles,
    scoring,
    searches,
    settings,
    sso,
    templates,
    webhooks,
    workspaces,
)
from app.api.routes.settings import suppressions_router
from app.api.v1 import routes as public_v1
from app.core.config import production_config_errors
from app.core.config import settings as app_settings
from app.core.errors import AppError
from app.core.exceptions import (
    app_error_handler,
    http_exception_handler,
    rate_limit_exceeded_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import setup_logging
from app.core.metrics import MetricsMiddleware
from app.core.middleware import RequestContextMiddleware
from app.core.observability import init_sentry
from app.core.rate_limit import limiter
from app.core.security import ensure_encryption_key_configured
from app.core.tracing import init_tracing

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    if app_settings.is_production:
        errors = production_config_errors(app_settings)
        if errors:
            raise RuntimeError("Invalid production configuration: " + "; ".join(errors))
        if app_settings.storage_backend != "s3":
            logging.getLogger(__name__).warning(
                "STORAGE_BACKEND is local: exported files live on this container's disk and "
                "are lost on redeploy. Configure S3/R2 for production.",
            )
    ensure_encryption_key_configured()
    yield


init_sentry("api")

app = FastAPI(
    title=app_settings.app_name,
    version="1.0.0",
    description="B2B lead-intelligence and outreach workflow API",
    lifespan=lifespan,
    docs_url="/docs" if app_settings.expose_api_docs else None,
    redoc_url="/redoc" if app_settings.expose_api_docs else None,
    openapi_url="/openapi.json" if app_settings.expose_api_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins,
    allow_origin_regex=app_settings.resolved_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "X-Workspace-Id",
        "X-Requested-With",
    ],
    expose_headers=["X-Request-ID", "Content-Disposition"],
)
app.add_middleware(MetricsMiddleware)
# Outermost: request ids and security headers apply to every response, including CORS errors.
app.add_middleware(RequestContextMiddleware, hsts=app_settings.is_production)
init_tracing("api", app=app)

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.state.limiter = limiter
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(health.router)
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(sso.router)
app.include_router(roles.router)
app.include_router(privacy.router)
app.include_router(notifications.router)
app.include_router(mailboxes.router)
app.include_router(inbox.router)
app.include_router(crm.router)
app.include_router(developer.router)
app.include_router(public_v1.router)
app.include_router(workspaces.router)
app.include_router(workspaces.invitations_router)
app.include_router(billing.router)
app.include_router(niches.router)
app.include_router(searches.router)
app.include_router(leads.router)
app.include_router(companies.router)
app.include_router(scoring.router)
app.include_router(emails.router)
app.include_router(approvals.router)
app.include_router(templates.router)
app.include_router(campaigns.router)
app.include_router(replies.router)
app.include_router(dashboard.router)
app.include_router(settings.router)
app.include_router(provider_settings.router)
app.include_router(suppressions_router)
app.include_router(compliance.router)
app.include_router(webhooks.router)
