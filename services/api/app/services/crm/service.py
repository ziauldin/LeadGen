"""Deals pipeline, tasks with reminders, notes, and the per-lead activity timeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.models.audit_log import AuditLog
from app.models.crm import Deal, DealStage, Note, Task
from app.models.email_message import EmailMessage
from app.models.enums import EmailMessageStatus
from app.models.lead import Lead
from app.models.reply import Reply
from app.models.user import User
from app.models.workspace import WorkspaceSettings
from app.services.workspaces.service import audit

DEFAULT_STAGES: list[tuple[str, str, int]] = [
    ("Interested", "open", 10),
    ("Meeting booked", "open", 30),
    ("Proposal", "open", 60),
    ("Negotiation", "open", 80),
    ("Won", "won", 100),
    ("Lost", "lost", 0),
]
SENT_LIKE = (EmailMessageStatus.SENT, EmailMessageStatus.BOUNCED, EmailMessageStatus.COMPLAINED)


def _now() -> datetime:
    return datetime.now(UTC)


def stages(db: Session, workspace_id: int) -> list[DealStage]:
    rows = list(
        db.scalars(
            select(DealStage)
            .where(DealStage.workspace_id == workspace_id)
            .order_by(DealStage.position)
        ).all()
    )
    if rows:
        return rows
    for position, (name, kind, probability) in enumerate(DEFAULT_STAGES):
        db.add(
            DealStage(
                workspace_id=workspace_id,
                name=name,
                kind=kind,
                probability=probability,
                position=position,
            )
        )
    db.flush()
    return list(
        db.scalars(
            select(DealStage)
            .where(DealStage.workspace_id == workspace_id)
            .order_by(DealStage.position)
        ).all()
    )


def stage(db: Session, workspace_id: int, stage_id: int) -> DealStage:
    row = db.scalar(
        select(DealStage).where(DealStage.id == stage_id, DealStage.workspace_id == workspace_id)
    )
    if row is None:
        raise ValidationFailedError("Unknown stage")
    return row


def get_deal(db: Session, workspace_id: int, deal_id: int) -> Deal:
    deal = db.scalar(select(Deal).where(Deal.id == deal_id, Deal.workspace_id == workspace_id))
    if deal is None:
        raise NotFoundError("Deal not found")
    return deal


def _check_lead(db: Session, workspace_id: int, lead_id: int | None) -> Lead | None:
    if lead_id is None:
        return None
    lead = db.scalar(select(Lead).where(Lead.id == lead_id, Lead.workspace_id == workspace_id))
    if lead is None:
        raise ValidationFailedError("Lead not found")
    return lead


def create_deal(
    db: Session,
    workspace_id: int,
    actor_id: int | None,
    data: dict[str, Any],
    *,
    source: str = "manual",
) -> Deal:
    lead = _check_lead(db, workspace_id, data.get("lead_id"))
    stage_id = data.get("stage_id") or stages(db, workspace_id)[0].id
    target = stage(db, workspace_id, stage_id)
    deal = Deal(
        workspace_id=workspace_id,
        title=(data.get("title") or (lead.full_name if lead else "New deal"))[:255],
        lead_id=lead.id if lead else None,
        company_id=data.get("company_id") or (lead.company_id if lead else None),
        stage_id=target.id,
        owner_id=data.get("owner_id", actor_id),
        value_cents=int(data.get("value_cents") or 0),
        currency=(data.get("currency") or "USD").upper()[:3],
        expected_close_date=data.get("expected_close_date"),
        position=0,
        source=source,
    )
    db.add(deal)
    db.flush()
    audit(
        db,
        workspace_id,
        actor_id,
        "deal_created",
        "deal",
        deal.id,
        {"stage": target.name, "lead_id": deal.lead_id, "source": source},
    )
    return deal


def update_deal(db: Session, deal: Deal, actor_id: int, changes: dict[str, Any]) -> Deal:
    previous_stage = deal.stage_id
    if "stage_id" in changes and changes["stage_id"] is not None:
        target = stage(db, deal.workspace_id, changes["stage_id"])
        deal.stage_id = target.id
        deal.closed_at = _now() if target.kind in ("won", "lost") else None
    if "lead_id" in changes:
        lead = _check_lead(db, deal.workspace_id, changes["lead_id"])
        deal.lead_id = lead.id if lead else None
    for field in (
        "title",
        "owner_id",
        "value_cents",
        "currency",
        "expected_close_date",
        "position",
    ):
        if field in changes:
            value = changes[field]
            if field == "currency" and value:
                value = value.upper()[:3]
            setattr(deal, field, value)
    meta: dict[str, Any] = {
        k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in changes.items()
    }
    if deal.stage_id != previous_stage:
        names = dict(
            db.execute(
                select(DealStage.id, DealStage.name).where(
                    DealStage.id.in_([previous_stage, deal.stage_id])
                )
            ).all()
        )
        meta.update({"from_stage": names.get(previous_stage), "to_stage": names.get(deal.stage_id)})
    audit(db, deal.workspace_id, actor_id, "deal_updated", "deal", deal.id, meta)
    db.commit()
    return deal


def auto_deal_from_reply(db: Session, reply: Reply) -> Deal | None:
    """An interested reply opens a deal for the lead, unless one is already open."""
    if reply.lead_id is None:
        return None
    settings_row = db.scalar(
        select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == reply.workspace_id)
    )
    if settings_row is not None and not settings_row.auto_create_deals:
        return None
    open_stage_ids = select(DealStage.id).where(
        DealStage.workspace_id == reply.workspace_id, DealStage.kind == "open"
    )
    existing = db.scalar(
        select(Deal.id).where(
            Deal.workspace_id == reply.workspace_id,
            Deal.lead_id == reply.lead_id,
            Deal.stage_id.in_(open_stage_ids),
        )
    )
    if existing:
        return None
    lead = db.get(Lead, reply.lead_id)
    company = lead.company.name if lead and lead.company else None
    title = f"{lead.full_name}{f' · {company}' if company else ''}" if lead else reply.from_email
    return create_deal(
        db,
        reply.workspace_id,
        None,
        {"lead_id": reply.lead_id, "title": title, "owner_id": None},
        source="reply",
    )


def board(db: Session, workspace_id: int) -> dict[str, Any]:
    rows = stages(db, workspace_id)
    deals = db.scalars(
        select(Deal)
        .where(Deal.workspace_id == workspace_id)
        .order_by(Deal.position, Deal.updated_at.desc())
    ).all()
    lead_names: dict[int | None, str] = (
        dict(
            db.execute(
                select(Lead.id, Lead.full_name).where(
                    Lead.id.in_({d.lead_id for d in deals if d.lead_id})
                )
            ).all()
        )
        if deals
        else {}
    )
    owners: dict[int | None, str] = (
        dict(
            db.execute(
                select(User.id, User.name).where(
                    User.id.in_({d.owner_id for d in deals if d.owner_id})
                )
            ).all()
        )
        if deals
        else {}
    )
    totals = {s.id: {"count": 0, "value_cents": 0} for s in rows}
    for deal in deals:
        if deal.stage_id in totals:
            totals[deal.stage_id]["count"] += 1
            totals[deal.stage_id]["value_cents"] += deal.value_cents
    weighted = sum(
        d.value_cents * next((s.probability for s in rows if s.id == d.stage_id), 0) // 100
        for d in deals
    )
    return {
        "stages": [
            {
                "id": s.id,
                "name": s.name,
                "kind": s.kind,
                "probability": s.probability,
                "position": s.position,
                **totals[s.id],
            }
            for s in rows
        ],
        "deals": [
            deal_payload(d, lead_names.get(d.lead_id), owners.get(d.owner_id)) for d in deals
        ],
        "weighted_pipeline_cents": weighted,
    }


def deal_payload(
    deal: Deal, lead_name: str | None = None, owner_name: str | None = None
) -> dict[str, Any]:
    return {
        "id": deal.id,
        "title": deal.title,
        "lead_id": deal.lead_id,
        "lead_name": lead_name,
        "company_id": deal.company_id,
        "stage_id": deal.stage_id,
        "owner_id": deal.owner_id,
        "owner_name": owner_name,
        "value_cents": deal.value_cents,
        "currency": deal.currency,
        "expected_close_date": deal.expected_close_date,
        "source": deal.source,
        "closed_at": deal.closed_at,
        "created_at": deal.created_at,
        "updated_at": deal.updated_at,
    }


# --- tasks ---------------------------------------------------------------------------------------


def due_reminders(db: Session, *, now: datetime | None = None) -> int:
    """Notify assignees of tasks that just became due (once per task)."""
    from app.services.notifications.service import notify

    now = now or _now()
    due = db.scalars(
        select(Task).where(
            Task.done_at.is_(None),
            Task.reminded_at.is_(None),
            Task.due_at.is_not(None),
            Task.due_at <= now,
            Task.assignee_id.is_not(None),
        )
    ).all()
    for task in due:
        notify(
            db,
            task.workspace_id,
            "task_due",
            f"Task due: {task.title}",
            body=task.notes,
            link=f"/leads/{task.lead_id}" if task.lead_id else "/tasks",
            user_ids=[task.assignee_id] if task.assignee_id else None,
        )
        task.reminded_at = now
    db.commit()
    return len(due)


# --- timeline ------------------------------------------------------------------------------------


@dataclass
class TimelineEvent:
    kind: str
    at: datetime
    title: str
    detail: str | None
    actor: str | None
    ref_id: int | None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def timeline(
    db: Session, workspace_id: int, lead_id: int, *, limit: int = 200
) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    names: dict[int | None, str] = dict(db.execute(select(User.id, User.name)).all())
    for m in db.scalars(
        select(EmailMessage).where(
            EmailMessage.workspace_id == workspace_id,
            EmailMessage.lead_id == lead_id,
            EmailMessage.status.in_(SENT_LIKE),
        )
    ).all():
        label = {"bounced": "Email bounced", "complained": "Marked as spam"}.get(
            str(m.status), "Email sent"
        )
        events.append(
            TimelineEvent(
                "email",
                m.sent_at or m.created_at,
                f"{label}: {m.subject}",
                m.body[:300],
                None,
                m.id,
            )
        )
    for r in db.scalars(
        select(Reply).where(Reply.workspace_id == workspace_id, Reply.lead_id == lead_id)
    ).all():
        events.append(
            TimelineEvent(
                "reply",
                r.received_at,
                f"Replied ({str(r.classification).replace('_', ' ')})",
                r.body[:300],
                r.from_email,
                r.id,
            )
        )
    for n in db.scalars(
        select(Note).where(Note.workspace_id == workspace_id, Note.lead_id == lead_id)
    ).all():
        events.append(
            TimelineEvent("note", n.created_at, "Note", n.body, names.get(n.author_id), n.id)
        )
    for t in db.scalars(
        select(Task).where(Task.workspace_id == workspace_id, Task.lead_id == lead_id)
    ).all():
        events.append(
            TimelineEvent(
                "task",
                t.created_at,
                f"Task: {t.title}",
                "Done" if t.done_at else (f"Due {t.due_at:%d %b %Y}" if t.due_at else None),
                names.get(t.created_by_id),
                t.id,
            )
        )
        if t.done_at:
            events.append(
                TimelineEvent(
                    "task_done",
                    t.done_at,
                    f"Completed: {t.title}",
                    None,
                    names.get(t.assignee_id),
                    t.id,
                )
            )
    deal_ids = list(
        db.scalars(
            select(Deal.id).where(Deal.workspace_id == workspace_id, Deal.lead_id == lead_id)
        ).all()
    )
    audit_filters = [(AuditLog.entity_type == "lead") & (AuditLog.entity_id == lead_id)]
    if deal_ids:
        audit_filters.append((AuditLog.entity_type == "deal") & (AuditLog.entity_id.in_(deal_ids)))
    from sqlalchemy import or_

    for log in db.scalars(
        select(AuditLog)
        .where(AuditLog.workspace_id == workspace_id, or_(*audit_filters))
        .order_by(AuditLog.created_at.desc())
        .limit(100)
    ).all():
        meta = log.metadata_ or {}
        if log.action == "deal_created":
            title = f"Deal opened in {meta.get('stage')}"
        elif log.action == "deal_updated" and meta.get("to_stage"):
            title = f"Deal moved to {meta['to_stage']}"
        elif log.action in ("lead_status_changed", "lead.status_changed") or "status" in meta:
            title = f"Status changed to {meta.get('to') or meta.get('status')}"
        else:
            continue
        events.append(
            TimelineEvent(
                "activity", log.created_at, title, None, names.get(log.actor_id), log.entity_id
            )
        )
    events.sort(key=lambda e: _aware(e.at), reverse=True)
    return events[:limit]


def pipeline_value(db: Session, workspace_id: int) -> int:
    return (
        db.scalar(
            select(func.coalesce(func.sum(Deal.value_cents), 0)).where(
                Deal.workspace_id == workspace_id
            )
        )
        or 0
    )


def maybe_auto_deal(db: Session, reply: Reply) -> None:
    """Best effort: interested replies open a deal when CRM is on for the workspace."""
    import logging

    from app.core.flags import feature_enabled
    from app.models.enums import ReplyClassification
    from app.models.workspace import Workspace

    if str(reply.classification) != ReplyClassification.POSITIVE or reply.is_auto_reply:
        return
    workspace = db.get(Workspace, reply.workspace_id)
    if workspace is None or not feature_enabled("crm", workspace):
        return
    try:
        with db.begin_nested():
            auto_deal_from_reply(db, reply)
    except Exception:
        logging.getLogger(__name__).exception("Could not open a deal from reply %s", reply.id)
