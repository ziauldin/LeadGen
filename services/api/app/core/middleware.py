"""ASGI middleware: request ids, access logs and security headers."""

from __future__ import annotations

import logging
import re
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.request_context import new_request_id, request_id_var, user_id_var, workspace_id_var

logger = logging.getLogger("app.request")

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    (b"cross-origin-opener-policy", b"same-origin"),
]


class RequestContextMiddleware:
    """Accept or create ``X-Request-ID``, expose it, and log one line per request."""

    def __init__(self, app: ASGIApp, *, hsts: bool = False) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = ""
        for name, value in scope.get("headers", []):
            if name == b"x-request-id":
                incoming = value.decode("latin-1")
                break
        request_id = incoming if _REQUEST_ID_RE.match(incoming) else new_request_id()

        token = request_id_var.set(request_id)
        user_token = user_id_var.set(None)
        ws_token = workspace_id_var.set(None)
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.perf_counter()
        status_holder = {"status": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                existing = {name for name, _ in headers}
                for name, value in SECURITY_HEADERS:
                    if name not in existing:
                        headers.append((name, value))
                if self.hsts:
                    headers.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
                    )
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            path = scope.get("path", "")
            if not path.startswith("/health"):
                logger.info(
                    "%s %s %s %sms",
                    scope.get("method"),
                    path,
                    status_holder["status"],
                    duration_ms,
                    extra={
                        "http_method": scope.get("method"),
                        "http_path": path,
                        "http_status": status_holder["status"],
                        "duration_ms": duration_ms,
                    },
                )
            request_id_var.reset(token)
            user_id_var.reset(user_token)
            workspace_id_var.reset(ws_token)
