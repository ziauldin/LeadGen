from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import (
    auth,
    campaigns,
    companies,
    compliance,
    dashboard,
    emails,
    health,
    leads,
    niches,
    provider_settings,
    replies,
    scoring,
    searches,
    settings,
)
from app.api.routes.settings import suppressions_router
from app.core.config import settings as app_settings
from app.core.exceptions import http_exception_handler, validation_exception_handler
from app.core.logging import setup_logging
from app.core.security import ensure_encryption_key_configured


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    ensure_encryption_key_configured()
    yield


app = FastAPI(
    title=app_settings.app_name,
    version="0.1.0",
    description="B2B lead-intelligence and outreach workflow API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins,
    allow_origin_regex=app_settings.resolved_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(niches.router)
app.include_router(searches.router)
app.include_router(leads.router)
app.include_router(companies.router)
app.include_router(scoring.router)
app.include_router(emails.router)
app.include_router(campaigns.router)
app.include_router(replies.router)
app.include_router(dashboard.router)
app.include_router(settings.router)
app.include_router(provider_settings.router)
app.include_router(suppressions_router)
app.include_router(compliance.router)
