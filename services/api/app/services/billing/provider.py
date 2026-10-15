"""Billing provider interface. Only a no-op implementation exists for now (Stripe is a follow-up)."""

from __future__ import annotations

from typing import Any, Protocol

from app.core.errors import AppError
from app.models.workspace import Workspace


class BillingNotConfiguredError(AppError):
    status_code = 501
    code = "billing_not_configured"


class BillingProvider(Protocol):
    def create_checkout(self, workspace: Workspace, plan: str) -> str: ...

    def handle_webhook(self, payload: bytes, signature: str) -> None: ...

    def get_subscription(self, workspace: Workspace) -> dict[str, Any] | None: ...


class NoopBillingProvider:
    def create_checkout(self, workspace: Workspace, plan: str) -> str:
        raise BillingNotConfiguredError(
            "Online billing isn't available yet. Contact support to upgrade."
        )

    def handle_webhook(self, payload: bytes, signature: str) -> None:
        raise BillingNotConfiguredError("Billing webhooks are not configured")

    def get_subscription(self, workspace: Workspace) -> dict[str, Any] | None:
        return None


def get_billing_provider() -> BillingProvider:
    return NoopBillingProvider()
