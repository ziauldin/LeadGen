"""Unauthenticated endpoints used by the marketing site: plans for the pricing page and contact."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, EmailStr, Field

from app.core.config import settings
from app.core.rate_limit import client_ip, enforce
from app.schemas.auth import MessageResponse
from app.services.auth.protection import verify_captcha
from app.services.billing.plans import PLAN_FEATURES, PLANS
from app.services.billing.stripe_billing import billing_enabled, prices
from app.services.platform_email.dispatch import send_platform_email
from app.services.platform_email.mailer import TransactionalEmail

router = APIRouter(tags=["public"])
logger = logging.getLogger(__name__)


class PublicPlan(BaseModel):
    name: str
    limits: dict[str, int]
    features: dict[str, bool | int]
    prices: dict[str, float | None] | None
    currency: str
    purchasable: list[str]


class ContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    company: str | None = Field(default=None, max_length=200)
    topic: str = Field(default="sales", pattern="^(sales|support|privacy|other)$")
    message: str = Field(min_length=10, max_length=5000)
    captcha_token: str | None = None
    # Hidden field: real people leave it empty.
    website: str | None = Field(default=None, max_length=200)


def _display_prices() -> dict[str, Any]:
    try:
        return json.loads(settings.plan_display_prices or "{}")
    except json.JSONDecodeError:
        logger.error("PLAN_DISPLAY_PRICES is not valid JSON")
        return {}


@router.get("/billing/plans", response_model=list[PublicPlan])
def public_plans() -> list[PublicPlan]:
    """Plans, limits and the prices shown on the pricing page (no sign-in needed)."""
    display = _display_prices()
    online = prices() if billing_enabled() else {}
    plans = []
    for name, limits in PLANS.items():
        shown = display.get(name)
        plans.append(
            PublicPlan(
                name=name,
                limits=limits.as_dict(),
                features=PLAN_FEATURES.get(name, PLAN_FEATURES["free"]).as_dict(),
                prices={"month": shown.get("month"), "year": shown.get("year")}
                if isinstance(shown, dict)
                else None,
                currency=str(display.get("currency", "USD")),
                purchasable=sorted(
                    key.split(":")[1] for key in online if key.startswith(f"{name}:")
                ),
            )
        )
    return plans


@router.post("/contact", response_model=MessageResponse)
def contact(payload: ContactRequest, request: Request) -> MessageResponse:
    ip = client_ip(request)
    enforce("5/hour", "contact", ip)
    if payload.website:  # bot filled the honeypot: pretend it worked
        return MessageResponse(message="Thanks, we'll be in touch.")
    verify_captcha(payload.captcha_token, remote_ip=ip)
    send_platform_email(
        TransactionalEmail(
            to=settings.support_email,
            subject=f"[{payload.topic}] Contact from {payload.name}",
            text=(
                f"Name: {payload.name}\nEmail: {payload.email}\nCompany: {payload.company or '-'}\n"
                f"Topic: {payload.topic}\n\n{payload.message}\n"
            ),
            tags={"kind": "contact"},
        )
    )
    return MessageResponse(message="Thanks, we'll be in touch.")
