import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError
from app.core.request_context import get_request_id

logger = logging.getLogger(__name__)


async def http_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101 - registered for this type only
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101 - registered for this type only
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


async def app_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)  # noqa: S101 - registered for this type only
    content: dict[str, object] = {"detail": exc.detail, "code": exc.code}
    if exc.extra:
        content.update(exc.extra)
    return JSONResponse(status_code=exc.status_code, content=content)


async def rate_limit_exceeded_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests. Please wait a moment and try again.",
            "code": "rate_limited",
        },
        headers={"Retry-After": "60"},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Never leak exception text; return a request id the user can quote to support."""
    # This handler runs in Starlette's outermost error middleware, after the request-context
    # middleware has unwound, so read the id from the shared ASGI scope instead.
    request_id = get_request_id() or request.scope.get("state", {}).get("request_id")
    logger.exception("Unhandled error rid=%s", request_id, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
        headers={"X-Request-ID": request_id} if request_id else None,
    )
