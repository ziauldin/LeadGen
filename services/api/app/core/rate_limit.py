"""Rate limiting (slowapi + limits). Redis-backed in production, in-memory in dev/test."""

from __future__ import annotations

from fastapi import Request
from limits import parse
from slowapi import Limiter

from app.core.config import settings
from app.core.errors import RateLimitedError


def client_ip(request: Request) -> str:
    """Client IP, honouring ``X-Forwarded-For`` from the configured number of trusted proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    hops = settings.trusted_proxy_hops
    if forwarded and hops > 0:
        parts = [part.strip() for part in forwarded.split(",") if part.strip()]
        if parts:
            return parts[-hops] if len(parts) >= hops else parts[0]
    return request.client.host if request.client else "unknown"


def workspace_or_ip_key(request: Request) -> str:
    """Default key: the workspace (set by auth middleware) if known, else the client IP."""
    workspace_id = getattr(request.state, "workspace_id", None)
    if workspace_id:
        return f"ws:{workspace_id}"
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return f"ip:{client_ip(request)}"


limiter = Limiter(
    key_func=client_ip,
    storage_uri=settings.resolved_rate_limit_storage,
    enabled=settings.rate_limit_enabled,
    headers_enabled=False,
    strategy="moving-window",
)


def enforce(limit: str, *keys: str) -> None:
    """Count one hit against ``limit`` for an arbitrary key (e.g. an email address)."""
    if not settings.rate_limit_enabled:
        return
    item = parse(limit)
    identifier = ":".join(keys)
    if not limiter.limiter.hit(item, "manual", identifier):
        raise RateLimitedError("Too many requests. Please wait a moment and try again.")


def reset_rate_limits() -> None:
    """Clear all counters (tests)."""
    limiter.reset()
