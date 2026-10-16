"""Outreach analytics: daily series, breakdowns, A/B variant results with a significance test."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.campaign import Campaign, CampaignStep
from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus, ReplyClassification
from app.models.provider_credential import ProviderCredential
from app.models.reply import Reply

SENT_LIKE = (EmailMessageStatus.SENT, EmailMessageStatus.BOUNCED, EmailMessageStatus.COMPLAINED)
MIN_SENDS_FOR_WINNER = 30
VARIANT_KEYS = ("A", "B", "C", "D")


def choose_variant(step: CampaignStep, seed: int) -> tuple[str, dict[str, Any] | None]:
    """Even, stable split: the same enrollment always gets the same variant of a step."""
    variants = [
        v for v in (step.variants or []) if v.get("subject_template") and v.get("body_template")
    ]
    if not variants:
        return "A", None
    options: list[tuple[str, dict[str, Any] | None]] = [
        ("A", None),
        *[(str(v["key"]), v) for v in variants],
    ]
    return options[seed % len(options)]


def _day(value: datetime) -> date:
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(UTC).date()


@dataclass
class Window:
    start: datetime
    end: datetime

    @classmethod
    def last(cls, days: int) -> Window:
        end = datetime.now(UTC)
        start = (end - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return cls(start, end)


def _sent_rows(
    db: Session, workspace_id: int, window: Window, campaign_id: int | None
) -> list[Any]:
    query = select(
        EmailMessage.id,
        EmailMessage.sent_at,
        EmailMessage.status,
        EmailMessage.campaign_id,
        EmailMessage.step_number,
        EmailMessage.variant,
        EmailMessage.sender_credential_id,
        EmailMessage.template_id,
    ).where(
        EmailMessage.workspace_id == workspace_id,
        EmailMessage.status.in_(SENT_LIKE),
        EmailMessage.sent_at >= window.start,
        EmailMessage.sent_at <= window.end,
    )
    if campaign_id:
        query = query.where(EmailMessage.campaign_id == campaign_id)
    return list(db.execute(query).all())


def _reply_rows(
    db: Session, workspace_id: int, window: Window, campaign_id: int | None
) -> list[Any]:
    query = (
        select(
            Reply.received_at,
            Reply.classification,
            Reply.email_message_id,
            EmailMessage.campaign_id,
        )
        .join(EmailMessage, EmailMessage.id == Reply.email_message_id, isouter=True)
        .where(
            Reply.workspace_id == workspace_id,
            Reply.received_at >= window.start,
            Reply.received_at <= window.end,
            Reply.is_auto_reply.is_(False),
        )
    )
    if campaign_id:
        query = query.where(EmailMessage.campaign_id == campaign_id)
    return list(db.execute(query).all())


def overview(
    db: Session, workspace_id: int, *, days: int = 30, campaign_id: int | None = None
) -> dict[str, Any]:
    window = Window.last(days)
    sent = _sent_rows(db, workspace_id, window, campaign_id)
    replies = _reply_rows(db, workspace_id, window, campaign_id)
    sent_ids = {row.id for row in sent}

    series: dict[date, dict[str, int]] = {}
    day = window.start.date()
    while day <= window.end.date():
        series[day] = {"sent": 0, "bounced": 0, "replies": 0, "positive": 0}
        day += timedelta(days=1)
    for row in sent:
        bucket = series.setdefault(
            _day(row.sent_at), {"sent": 0, "bounced": 0, "replies": 0, "positive": 0}
        )
        bucket["sent"] += 1
        if row.status in (EmailMessageStatus.BOUNCED, EmailMessageStatus.COMPLAINED):
            bucket["bounced"] += 1
    for row in replies:
        bucket = series.setdefault(
            _day(row.received_at), {"sent": 0, "bounced": 0, "replies": 0, "positive": 0}
        )
        bucket["replies"] += 1
        if row.classification == ReplyClassification.POSITIVE:
            bucket["positive"] += 1

    # Replies attributed to the email they answer, for per-dimension rates.
    replied: dict[int, str] = {
        r.email_message_id: str(r.classification) for r in replies if r.email_message_id in sent_ids
    }

    def breakdown(key: str) -> list[dict[str, Any]]:
        groups: dict[Any, dict[str, int]] = {}
        for row in sent:
            value = getattr(row, key)
            group = groups.setdefault(value, {"sent": 0, "bounced": 0, "replies": 0, "positive": 0})
            group["sent"] += 1
            if row.status in (EmailMessageStatus.BOUNCED, EmailMessageStatus.COMPLAINED):
                group["bounced"] += 1
            if row.id in replied:
                group["replies"] += 1
                if replied[row.id] == ReplyClassification.POSITIVE:
                    group["positive"] += 1
        return [{"key": k, **v, **_rates(v)} for k, v in groups.items()]

    campaigns = dict(
        db.execute(
            select(Campaign.id, Campaign.name).where(Campaign.workspace_id == workspace_id)
        ).all()
    )
    mailboxes = dict(
        db.execute(
            select(ProviderCredential.id, ProviderCredential.display_name).where(
                ProviderCredential.workspace_id == workspace_id
            )
        ).all()
    )
    totals = {
        k: sum(b[k] for b in series.values()) for k in ("sent", "bounced", "replies", "positive")
    }
    return {
        "days": days,
        "totals": {**totals, **_rates(totals)},
        "series": [{"date": d.isoformat(), **v} for d, v in sorted(series.items())],
        "by_campaign": sorted(
            (
                {**g, "label": campaigns.get(g["key"], "Manual and inbox emails")}
                for g in breakdown("campaign_id")
            ),
            key=lambda g: -g["sent"],
        ),
        "by_step": sorted(
            (
                {**g, "label": f"Step {g['key']}" if g["key"] else "Other"}
                for g in breakdown("step_number")
            ),
            key=lambda g: g["key"] or 99,
        ),
        "by_variant": sorted(
            ({**g, "label": g["key"] or "A"} for g in breakdown("variant")),
            key=lambda g: g["label"],
        ),
        "by_mailbox": sorted(
            (
                {**g, "label": mailboxes.get(g["key"], "Default sender")}
                for g in breakdown("sender_credential_id")
            ),
            key=lambda g: -g["sent"],
        ),
        "by_template": sorted(
            ({**g, "label": g["key"] or "Custom / AI"} for g in breakdown("template_id")),
            key=lambda g: -g["sent"],
        ),
    }


def _rates(counts: dict[str, Any]) -> dict[str, float]:
    sent = counts.get("sent", 0)
    return {
        "reply_rate": round(counts.get("replies", 0) / sent, 4) if sent else 0.0,
        "positive_rate": round(counts.get("positive", 0) / sent, 4) if sent else 0.0,
        "bounce_rate": round(counts.get("bounced", 0) / sent, 4) if sent else 0.0,
    }


def two_proportion_p_value(
    successes_a: int, total_a: int, successes_b: int, total_b: int
) -> float | None:
    """Two-sided p-value for a difference between two rates (normal approximation)."""
    if total_a == 0 or total_b == 0:
        return None
    pooled = (successes_a + successes_b) / (total_a + total_b)
    if pooled in (0, 1):
        return 1.0
    se = math.sqrt(pooled * (1 - pooled) * (1 / total_a + 1 / total_b))
    z = (successes_a / total_a - successes_b / total_b) / se
    return math.erfc(abs(z) / math.sqrt(2))


def variant_results(db: Session, workspace_id: int, campaign_id: int) -> list[dict[str, Any]]:
    """Per step: each variant's sends, replies and positive replies, and a winner if one is clear."""
    rows = db.execute(
        select(
            EmailMessage.step_number,
            EmailMessage.variant,
            func.count(EmailMessage.id),
            func.sum(
                case(
                    (
                        EmailMessage.status.in_(
                            [EmailMessageStatus.BOUNCED, EmailMessageStatus.COMPLAINED]
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
        )
        .where(
            EmailMessage.workspace_id == workspace_id,
            EmailMessage.campaign_id == campaign_id,
            EmailMessage.status.in_(SENT_LIKE),
        )
        .group_by(EmailMessage.step_number, EmailMessage.variant)
    ).all()
    reply_rows = db.execute(
        select(
            EmailMessage.step_number,
            EmailMessage.variant,
            func.count(Reply.id),
            func.sum(case((Reply.classification == ReplyClassification.POSITIVE, 1), else_=0)),
        )
        .join(EmailMessage, EmailMessage.id == Reply.email_message_id)
        .where(
            Reply.workspace_id == workspace_id,
            EmailMessage.campaign_id == campaign_id,
            Reply.is_auto_reply.is_(False),
        )
        .group_by(EmailMessage.step_number, EmailMessage.variant)
    ).all()
    replies = {
        (step, variant or "A"): (int(n or 0), int(pos or 0)) for step, variant, n, pos in reply_rows
    }
    steps: dict[int, list[dict[str, Any]]] = {}
    for step_number, raw_variant, sent, bounced in rows:
        variant = raw_variant or "A"
        n_replies, n_positive = replies.get((step_number, variant), (0, 0))
        stats = {
            "variant": variant,
            "sent": int(sent),
            "bounced": int(bounced or 0),
            "replies": n_replies,
            "positive": n_positive,
        }
        steps.setdefault(step_number or 0, []).append({**stats, **_rates(stats)})

    results = []
    for step_number, variants in sorted(steps.items()):
        variants.sort(key=lambda v: v["variant"])
        winner = None
        if len(variants) > 1 and all(v["sent"] >= MIN_SENDS_FOR_WINNER for v in variants):
            ranked = sorted(variants, key=lambda v: v["reply_rate"], reverse=True)
            best, runner_up = ranked[0], ranked[1]
            p_value = two_proportion_p_value(
                best["replies"], best["sent"], runner_up["replies"], runner_up["sent"]
            )
            if (
                p_value is not None
                and p_value < 0.05
                and best["reply_rate"] > runner_up["reply_rate"]
            ):
                winner = {"variant": best["variant"], "p_value": round(p_value, 4)}
        results.append(
            {
                "step_number": step_number,
                "variants": variants,
                "winner": winner,
                "min_sends": MIN_SENDS_FOR_WINNER,
            }
        )
    return results


def export_rows(db: Session, workspace_id: int, *, days: int) -> list[dict[str, Any]]:
    data = overview(db, workspace_id, days=days)
    return [
        {
            "date": row["date"],
            "sent": row["sent"],
            "bounced": row["bounced"],
            "replies": row["replies"],
            "positive": row["positive"],
        }
        for row in data["series"]
    ]


def weekly_report_lines(db: Session, workspace_id: int) -> list[str]:
    """Extra lines for the weekly digest: rates, the best campaign and any clear A/B winners."""
    data = overview(db, workspace_id, days=7)
    totals = data["totals"]
    if not totals["sent"]:
        return []
    lines = [
        f"Reply rate: {totals['reply_rate']:.1%} (interested {totals['positive_rate']:.1%})",
        f"Bounce rate: {totals['bounce_rate']:.1%}",
    ]
    campaigns = [c for c in data["by_campaign"] if c["key"] and c["sent"] >= 10]
    if campaigns:
        best = max(campaigns, key=lambda c: c["reply_rate"])
        lines.append(f"Best campaign: {best['label']} ({best['reply_rate']:.1%} replied)")
    for campaign in data["by_campaign"]:
        if not campaign["key"]:
            continue
        for step in variant_results(db, workspace_id, campaign["key"]):
            if step["winner"]:
                lines.append(
                    f"A/B winner: {campaign['label']}, step {step['step_number']}: "
                    f"version {step['winner']['variant']}"
                )
    return lines
