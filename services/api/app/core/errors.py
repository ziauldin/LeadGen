"""Domain errors raised by services and mapped to HTTP responses in one place."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for expected, user-facing errors."""

    status_code: int = 400
    code: str = "bad_request"

    def __init__(self, detail: str, *, extra: dict[str, Any] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.extra = extra or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "forbidden"


class AuthenticationError(AppError):
    status_code = 401
    code = "unauthorized"


class ValidationFailedError(AppError):
    status_code = 400
    code = "validation_failed"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


class QuotaExceededError(AppError):
    status_code = 402
    code = "quota_exceeded"

    def __init__(self, metric: str, limit: int, used: int) -> None:
        super().__init__(
            f"Plan limit reached for {metric.replace('_', ' ')} ({used}/{limit})",
            extra={"metric": metric, "limit": limit, "used": used},
        )


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"


class ProviderError(AppError):
    """A third-party provider (email, search, LLM) failed."""

    status_code = 502
    code = "provider_error"
