"""CRM-lite: deals board, tasks, notes and the lead activity timeline."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace, require_permission
from app.core.database import get_db
from app.core.errors import NotFoundError, ValidationFailedError
from app.core.flags import feature_enabled
from app.core.permissions import Permission
from app.core.tenancy import WorkspaceContext
from app.models.crm import Deal, DealStage, Note, Task
from app.models.lead import Lead
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.services.crm import service as crm
from app.services.workspaces.service import audit

router = APIRouter(tags=["crm"])
WRITE = Depends(require_permission(Permission.LEADS_WRITE))


def _enabled(ctx: WorkspaceContext = Depends(get_current_workspace)) -> WorkspaceContext:
    if not feature_enabled("crm", ctx.workspace):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deals and tasks aren't enabled"
        )
    return ctx


class StageRead(BaseModel):
    id: int
    name: str
    kind: str
    probability: int
    position: int
    count: int = 0
    value_cents: int = 0


class StageWrite(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    probability: int = Field(default=10, ge=0, le=100)


class DealRead(BaseModel):
    id: int
    title: str
    lead_id: int | None
    lead_name: str | None
    company_id: int | None
    stage_id: int
    owner_id: int | None
    owner_name: str | None
    value_cents: int
    currency: str
    expected_close_date: date | None
    source: str
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class Board(BaseModel):
    stages: list[StageRead]
    deals: list[DealRead]
    weighted_pipeline_cents: int


class DealWrite(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    lead_id: int | None = None
    company_id: int | None = None
    stage_id: int | None = None
    owner_id: int | None = None
    value_cents: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    expected_close_date: date | None = None
    position: int | None = None


class TaskRead(BaseModel):
    id: int
    title: str
    notes: str | None
    due_at: datetime | None
    done_at: datetime | None
    assignee_id: int | None
    assignee_name: str | None
    lead_id: int | None
    lead_name: str | None
    deal_id: int | None
    created_at: datetime


class TaskWrite(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=5000)
    due_at: datetime | None = None
    assignee_id: int | None = None
    lead_id: int | None = None
    deal_id: int | None = None
    done: bool | None = None


class NoteRead(BaseModel):
    id: int
    body: str
    author_id: int | None
    author_name: str | None
    lead_id: int | None
    deal_id: int | None
    created_at: datetime


class NoteWrite(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)
    deal_id: int | None = None


class TimelineItem(BaseModel):
    kind: str
    at: datetime
    title: str
    detail: str | None
    actor: str | None
    ref_id: int | None


def _member(db: Session, ctx: WorkspaceContext, user_id: int | None) -> None:
    if user_id is None:
        return
    if (
        db.scalar(
            select(WorkspaceMember.id).where(
                WorkspaceMember.workspace_id == ctx.workspace_id, WorkspaceMember.user_id == user_id
            )
        )
        is None
    ):
        raise ValidationFailedError("Choose someone in this workspace")


# --- stages & deals ------------------------------------------------------------------------------


@router.get("/deals/board", response_model=Board)
def deals_board(ctx: WorkspaceContext = Depends(_enabled), db: Session = Depends(get_db)) -> Board:
    data = crm.board(db, ctx.workspace_id)
    db.commit()  # default stages may have been created
    return Board(**data)


@router.post("/deals/stages", response_model=StageRead, status_code=status.HTTP_201_CREATED)
def add_stage(
    payload: StageWrite,
    ctx: WorkspaceContext = Depends(_enabled),
    db: Session = Depends(get_db),
    _a: WorkspaceContext = Depends(require_permission(Permission.SETTINGS_MANAGE)),
) -> StageRead:
    existing = crm.stages(db, ctx.workspace_id)
    open_count = sum(1 for s in existing if s.kind == "open")
    for s in existing:  # new open stages go before Won / Lost
        if s.position >= open_count:
            s.position += 1
    row = DealStage(
        workspace_id=ctx.workspace_id,
        name=payload.name,
        probability=payload.probability,
        kind="open",
        position=open_count,
    )
    db.add(row)
    db.commit()
    return StageRead(
        id=row.id, name=row.name, kind=row.kind, probability=row.probability, position=row.position
    )


@router.patch("/deals/stages/{stage_id}", response_model=StageRead)
def rename_stage(
    stage_id: int,
    payload: StageWrite,
    ctx: WorkspaceContext = Depends(_enabled),
    db: Session = Depends(get_db),
    _a: WorkspaceContext = Depends(require_permission(Permission.SETTINGS_MANAGE)),
) -> StageRead:
    row = crm.stage(db, ctx.workspace_id, stage_id)
    row.name = payload.name
    row.probability = payload.probability
    db.commit()
    return StageRead(
        id=row.id, name=row.name, kind=row.kind, probability=row.probability, position=row.position
    )


@router.post("/deals", response_model=DealRead, status_code=status.HTTP_201_CREATED)
def create_deal(
    payload: DealWrite,
    ctx: WorkspaceContext = Depends(_enabled),
    db: Session = Depends(get_db),
    _a: WorkspaceContext = WRITE,
) -> DealRead:
    _member(db, ctx, payload.owner_id)
    deal = crm.create_deal(
        db, ctx.workspace_id, ctx.user_id, payload.model_dump(exclude_unset=True)
    )
    db.commit()
    return _deal(db, deal)


def _deal(db: Session, deal: Deal) -> DealRead:
    lead_name = (
        db.scalar(select(Lead.full_name).where(Lead.id == deal.lead_id)) if deal.lead_id else None
    )
    owner_name = (
        db.scalar(select(User.name).where(User.id == deal.owner_id)) if deal.owner_id else None
    )
    return DealRead(**crm.deal_payload(deal, lead_name, owner_name))


@router.patch("/deals/{deal_id}", response_model=DealRead)
def update_deal(
    deal_id: int,
    payload: DealWrite,
    ctx: WorkspaceContext = Depends(_enabled),
    db: Session = Depends(get_db),
    _a: WorkspaceContext = WRITE,
) -> DealRead:
    changes = payload.model_dump(exclude_unset=True)
    _member(db, ctx, changes.get("owner_id"))
    deal = crm.update_deal(db, crm.get_deal(db, ctx.workspace_id, deal_id), ctx.user_id, changes)
    return _deal(db, deal)


@router.delete("/deals/{deal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deal(
    deal_id: int,
    ctx: WorkspaceContext = Depends(_enabled),
    db: Session = Depends(get_db),
    _a: WorkspaceContext = WRITE,
) -> None:
    deal = crm.get_deal(db, ctx.workspace_id, deal_id)
    db.delete(deal)
    audit(db, ctx.workspace_id, ctx.user_id, "deal_deleted", "deal", deal_id, {"title": deal.title})
    db.commit()


# --- tasks ---------------------------------------------------------------------------------------


def _task_rows(db: Session, tasks: list[Task]) -> list[TaskRead]:
    users = (
        dict(
            db.execute(
                select(User.id, User.name).where(
                    User.id.in_({t.assignee_id for t in tasks if t.assignee_id})
                )
            ).all()
        )
        if tasks
        else {}
    )
    leads = (
        dict(
            db.execute(
                select(Lead.id, Lead.full_name).where(
                    Lead.id.in_({t.lead_id for t in tasks if t.lead_id})
                )
            ).all()
        )
        if tasks
        else {}
    )
    return [
        TaskRead(
            id=t.id,
            title=t.title,
            notes=t.notes,
            due_at=t.due_at,
            done_at=t.done_at,
            assignee_id=t.assignee_id,
            assignee_name=users.get(t.assignee_id) if t.assignee_id else None,
            lead_id=t.lead_id,
            lead_name=leads.get(t.lead_id) if t.lead_id else None,
            deal_id=t.deal_id,
            created_at=t.created_at,
        )
        for t in tasks
    ]


@router.get("/tasks", response_model=list[TaskRead])
def list_tasks(
    scope: Literal["mine", "all"] = "mine",
    state: Literal["open", "done", "all"] = "open",
    due: Literal["overdue", "today", "upcoming", "any"] = "any",
    lead_id: int | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    ctx: WorkspaceContext = Depends(_enabled),
    db: Session = Depends(get_db),
) -> list[TaskRead]:
    now = datetime.now(UTC)
    end_of_day = now.replace(hour=23, minute=59, second=59)
    conditions: list[Any] = [Task.workspace_id == ctx.workspace_id]
    if scope == "mine" and lead_id is None:
        conditions.append(Task.assignee_id == ctx.user_id)
    if lead_id is not None:
        conditions.append(Task.lead_id == lead_id)
    if state == "open":
        conditions.append(Task.done_at.is_(None))
    elif state == "done":
        conditions.append(Task.done_at.is_not(None))
    if due == "overdue":
        conditions.extend([Task.due_at < now, Task.done_at.is_(None)])
    elif due == "today":
        conditions.extend(
            [
                Task.due_at >= now - timedelta(hours=now.hour, minutes=now.minute),
                Task.due_at <= end_of_day,
            ]
        )
    elif due == "upcoming":
        conditions.append(Task.due_at > end_of_day)
    tasks = list(
        db.scalars(
            select(Task)
            .where(*conditions)
            .order_by(Task.done_at.is_not(None), Task.due_at.is_(None), Task.due_at, Task.id)
            .limit(limit)
        ).all()
    )
    return _task_rows(db, tasks)


@router.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskWrite,
    ctx: WorkspaceContext = Depends(_enabled),
    db: Session = Depends(get_db),
    _a: WorkspaceContext = WRITE,
) -> TaskRead:
    if not payload.title:
        raise ValidationFailedError("Give the task a title")
    assignee = payload.assignee_id if "assignee_id" in payload.model_fields_set else ctx.user_id
    _member(db, ctx, assignee)
    if (
        payload.lead_id is not None
        and db.scalar(
            select(Lead.id).where(Lead.id == payload.lead_id, Lead.workspace_id == ctx.workspace_id)
        )
        is None
    ):
        raise ValidationFailedError("Lead not found")
    if payload.deal_id is not None:
        crm.get_deal(db, ctx.workspace_id, payload.deal_id)
    task = Task(
        workspace_id=ctx.workspace_id,
        title=payload.title,
        notes=payload.notes,
        due_at=payload.due_at,
        assignee_id=assignee,
        created_by_id=ctx.user_id,
        lead_id=payload.lead_id,
        deal_id=payload.deal_id,
    )
    db.add(task)
    db.commit()
    return _task_rows(db, [task])[0]


def _task(db: Session, ctx: WorkspaceContext, task_id: int) -> Task:
    task = db.scalar(select(Task).where(Task.id == task_id, Task.workspace_id == ctx.workspace_id))
    if task is None:
        raise NotFoundError("Task not found")
    return task


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: int,
    payload: TaskWrite,
    ctx: WorkspaceContext = Depends(_enabled),
    db: Session = Depends(get_db),
    _a: WorkspaceContext = WRITE,
) -> TaskRead:
    task = _task(db, ctx, task_id)
    changes = payload.model_dump(exclude_unset=True)
    if "assignee_id" in changes:
        _member(db, ctx, changes["assignee_id"])
    for field in ("title", "notes", "assignee_id"):
        if field in changes:
            setattr(task, field, changes[field])
    if "due_at" in changes:
        task.due_at = changes["due_at"]
        task.reminded_at = None
    if "done" in changes:
        task.done_at = datetime.now(UTC) if changes["done"] else None
    db.commit()
    return _task_rows(db, [task])[0]


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    ctx: WorkspaceContext = Depends(_enabled),
    db: Session = Depends(get_db),
    _a: WorkspaceContext = WRITE,
) -> None:
    db.delete(_task(db, ctx, task_id))
    db.commit()


# --- notes & timeline ----------------------------------------------------------------------------


def _lead(db: Session, ctx: WorkspaceContext, lead_id: int) -> Lead:
    lead = db.scalar(select(Lead).where(Lead.id == lead_id, Lead.workspace_id == ctx.workspace_id))
    if lead is None:
        raise NotFoundError("Lead not found")
    return lead


def _note_rows(db: Session, notes: list[Note]) -> list[NoteRead]:
    names = (
        dict(
            db.execute(
                select(User.id, User.name).where(
                    User.id.in_({n.author_id for n in notes if n.author_id})
                )
            ).all()
        )
        if notes
        else {}
    )
    return [
        NoteRead(
            id=n.id,
            body=n.body,
            author_id=n.author_id,
            author_name=names.get(n.author_id) if n.author_id else None,
            lead_id=n.lead_id,
            deal_id=n.deal_id,
            created_at=n.created_at,
        )
        for n in notes
    ]


@router.get("/leads/{lead_id}/notes", response_model=list[NoteRead])
def list_notes(
    lead_id: int, ctx: WorkspaceContext = Depends(_enabled), db: Session = Depends(get_db)
) -> list[NoteRead]:
    _lead(db, ctx, lead_id)
    notes = list(
        db.scalars(
            select(Note)
            .where(Note.workspace_id == ctx.workspace_id, Note.lead_id == lead_id)
            .order_by(Note.created_at.desc())
        ).all()
    )
    return _note_rows(db, notes)


@router.post("/leads/{lead_id}/notes", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def add_note(
    lead_id: int,
    payload: NoteWrite,
    ctx: WorkspaceContext = Depends(_enabled),
    db: Session = Depends(get_db),
    _a: WorkspaceContext = WRITE,
) -> NoteRead:
    _lead(db, ctx, lead_id)
    if payload.deal_id is not None:
        crm.get_deal(db, ctx.workspace_id, payload.deal_id)
    note = Note(
        workspace_id=ctx.workspace_id,
        body=payload.body.strip(),
        author_id=ctx.user_id,
        lead_id=lead_id,
        deal_id=payload.deal_id,
    )
    db.add(note)
    db.commit()
    return _note_rows(db, [note])[0]


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: int,
    ctx: WorkspaceContext = Depends(_enabled),
    db: Session = Depends(get_db),
    _a: WorkspaceContext = WRITE,
) -> None:
    note = db.scalar(select(Note).where(Note.id == note_id, Note.workspace_id == ctx.workspace_id))
    if note is None:
        raise NotFoundError("Note not found")
    if note.author_id != ctx.user_id and not ctx.can(Permission.SETTINGS_MANAGE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own notes"
        )
    db.delete(note)
    db.commit()


@router.get("/leads/{lead_id}/timeline", response_model=list[TimelineItem])
def lead_timeline(
    lead_id: int, ctx: WorkspaceContext = Depends(_enabled), db: Session = Depends(get_db)
) -> list[TimelineItem]:
    _lead(db, ctx, lead_id)
    return [TimelineItem(**event.__dict__) for event in crm.timeline(db, ctx.workspace_id, lead_id)]
