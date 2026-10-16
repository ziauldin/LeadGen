"""Prepaid credits for platform-paid services, used once a plan's included allowance runs out.

One credit buys one platform email verification, one platform email lookup or 1,000 platform AI
tokens. Usage on a workspace's own keys is never metered, so it never uses credits. Purchased
credits don't expire.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.billing import CreditTransaction
from app.models.workspace import Workspace

# How many units of a metric one credit buys.
CREDIT_UNITS: dict[str, int] = {
    "monthly_verifications": 1,
    "daily_hunter_lookups": 1,
    "monthly_llm_tokens": 1_000,
}


@dataclass(frozen=True)
class CreditPack:
    credits: int
    amount: float | None  # display price in PLAN_DISPLAY_PRICES' currency
    price_id: str | None  # Stripe price for a one-off payment


@lru_cache(maxsize=4)
def _parse_packs(raw_packs: str, raw_prices: str) -> tuple[CreditPack, ...]:
    try:
        packs = json.loads(raw_packs or "[]")
        stripe_prices = json.loads(raw_prices or "{}")
    except ValueError:
        return ()
    result = []
    for pack in packs if isinstance(packs, list) else []:
        try:
            credits = int(pack["credits"])
        except (KeyError, TypeError, ValueError):
            continue
        if credits <= 0:
            continue
        amount = pack.get("amount")
        result.append(
            CreditPack(
                credits=credits,
                amount=float(amount) if isinstance(amount, int | float) else None,
                price_id=stripe_prices.get(str(credits))
                if isinstance(stripe_prices, dict)
                else None,
            )
        )
    return tuple(sorted(result, key=lambda p: p.credits))


def credit_packs() -> tuple[CreditPack, ...]:
    return _parse_packs(settings.credit_packs, settings.stripe_credit_prices)


def pack_for(credits: int) -> CreditPack | None:
    return next((p for p in credit_packs() if p.credits == credits), None)


def credits_for(metric: str, units: int) -> int:
    """Credits needed for ``units`` of ``metric`` (rounded up)."""
    if units <= 0:
        return 0
    return math.ceil(units / CREDIT_UNITS[metric])


def balance(db: Session, workspace_id: int) -> int:
    return int(db.scalar(select(Workspace.credit_balance).where(Workspace.id == workspace_id)) or 0)


def _apply(db: Session, workspace_id: int, delta: int) -> int:
    db.execute(
        update(Workspace)
        .where(Workspace.id == workspace_id)
        .values(credit_balance=Workspace.credit_balance + delta)
        .execution_options(synchronize_session=False)
    )
    new_balance = balance(db, workspace_id)
    workspace = db.get(Workspace, workspace_id)
    if workspace is not None:
        db.expire(workspace, ["credit_balance"])
    return new_balance


def charge(db: Session, workspace_id: int, metric: str, credits: int) -> None:
    """Take credits for usage beyond the plan. Daily usage is kept on one ledger row per metric."""
    if credits <= 0:
        return
    new_balance = _apply(db, workspace_id, -credits)
    reference = f"usage:{metric}:{datetime.now(UTC):%Y-%m-%d}"
    row = db.scalar(
        select(CreditTransaction).where(
            CreditTransaction.workspace_id == workspace_id,
            CreditTransaction.reference == reference,
        )
    )
    if row is None:
        try:
            with db.begin_nested():
                db.add(
                    CreditTransaction(
                        workspace_id=workspace_id,
                        amount=-credits,
                        kind="usage",
                        metric=metric,
                        reference=reference,
                        balance_after=new_balance,
                    )
                )
            return
        except IntegrityError:
            row = db.scalar(
                select(CreditTransaction).where(
                    CreditTransaction.workspace_id == workspace_id,
                    CreditTransaction.reference == reference,
                )
            )
    if row is not None:
        row.amount -= credits
        row.balance_after = new_balance
    db.flush()


def grant(
    db: Session,
    workspace_id: int,
    credits: int,
    *,
    kind: str,
    reference: str | None = None,
    actor_id: int | None = None,
    note: str | None = None,
) -> bool:
    """Add (or, for adjustments, remove) credits. False if ``reference`` was already applied."""
    if reference and db.scalar(
        select(CreditTransaction.id).where(
            CreditTransaction.workspace_id == workspace_id,
            CreditTransaction.reference == reference,
        )
    ):
        return False
    new_balance = _apply(db, workspace_id, credits)
    db.add(
        CreditTransaction(
            workspace_id=workspace_id,
            amount=credits,
            kind=kind,
            reference=reference,
            note=(note or "")[:255] or None,
            actor_id=actor_id,
            balance_after=new_balance,
        )
    )
    db.flush()
    return True


def history(db: Session, workspace_id: int, limit: int = 50) -> list[CreditTransaction]:
    return list(
        db.scalars(
            select(CreditTransaction)
            .where(CreditTransaction.workspace_id == workspace_id)
            .order_by(CreditTransaction.created_at.desc(), CreditTransaction.id.desc())
            .limit(limit)
        ).all()
    )


def pack_payload(pack: CreditPack, purchasable: bool) -> dict[str, Any]:
    return {
        "credits": pack.credits,
        "amount": pack.amount,
        "purchasable": purchasable and bool(pack.price_id),
    }
