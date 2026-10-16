"""Errors shared by the billing routes. Stripe is implemented in ``stripe_billing``."""

from __future__ import annotations

from app.core.errors import AppError


class BillingNotConfiguredError(AppError):
    status_code = 501
    code = "billing_not_configured"
