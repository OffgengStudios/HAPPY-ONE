from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.core.errors import ApiError
from app.modules.demand.service import changed, writable
from app.modules.iam.dependencies import Database, Principal, require
from app.modules.iam.models import now
from app.modules.iam.service import page_query
from app.modules.work import schemas as data
from app.modules.work import service as s
from app.modules.work.models import Handoff, Notification, Task

router = APIRouter(tags=["work"])
TaskRead = Annotated[Principal, Depends(require("task:view"))]
TaskEdit = Annotated[Principal, Depends(require("task:view", "task:edit"))]
HandoffRead = Annotated[Principal, Depends(require("handoff:view"))]
HandoffEdit = Annotated[Principal, Depends(require("handoff:view", "handoff:manage"))]
NotifyRead = Annotated[Principal, Depends(require("notification:view"))]
Limit = Annotated[int, Query(ge=1, le=100)]


def _task(db: Database, identifier: UUID, actor: Principal) -> Task:
    row = db.scalar(
        select(Task).where(Task.id == identifier, Task.archived_at.is_(None), s.task_scope(actor))
    )
    if not row:
        raise ApiError(404, "TASK_NOT_FOUND", "Task not found.")
    return row


def _handoff(db: Database, identifier: UUID, actor: Principal) -> Handoff:
    row = db.scalar(
        select(Handoff).where(
            Handoff.id == identifier, Handoff.archived_at.is_(None), s.handoff_scope(actor)
        )
    )
    if not row:
        raise ApiError(404, "HANDOFF_NOT_FOUND", "Handoff not found.")
    return row


@router.get("/tasks")
def tasks(
    db: Database, actor: TaskRead, limit: Limit = 50, cursor: str | None = None
) -> dict[str, Any]:
    page = page_query(
        select(Task).where(Task.archived_at.is_(None), s.task_scope(actor)), Task, db, limit, cursor
    )
    return {"items": [s.view(row) for row in page["rows"]], "next_cursor": page["next_cursor"]}


@router.post("/tasks", status_code=201)
def create_task(
    values: data.TaskCreate, db: Database, actor: TaskEdit, request: Request
) -> dict[str, Any]:
    return s.view(s.create_task(db, values, actor, request))


@router.patch("/tasks/{identifier}")
def update_task(
    identifier: UUID, values: data.TaskUpdate, db: Database, actor: TaskEdit, request: Request
) -> dict[str, Any]:
    return s.view(s.update_task(db, _task(db, identifier, actor), values, actor, request))


@router.post("/tasks/{identifier}/claim")
def claim_task(
    identifier: UUID, values: data.VersionInput, db: Database, actor: TaskEdit, request: Request
) -> dict[str, Any]:
    return s.view(
        s.task_transition(db, _task(db, identifier, actor), "claim", values.version, actor, request)
    )


@router.post("/tasks/{identifier}/complete")
def complete_task(
    identifier: UUID, values: data.VersionInput, db: Database, actor: TaskEdit, request: Request
) -> dict[str, Any]:
    return s.view(
        s.task_transition(
            db, _task(db, identifier, actor), "complete", values.version, actor, request
        )
    )


@router.get("/handoffs")
def handoffs(
    db: Database, actor: HandoffRead, limit: Limit = 50, cursor: str | None = None
) -> dict[str, Any]:
    page = page_query(
        select(Handoff).where(Handoff.archived_at.is_(None), s.handoff_scope(actor)),
        Handoff,
        db,
        limit,
        cursor,
    )
    return {"items": [s.view(row) for row in page["rows"]], "next_cursor": page["next_cursor"]}


@router.post("/handoffs", status_code=201)
def create_handoff(
    values: data.HandoffCreate, db: Database, actor: HandoffEdit, request: Request
) -> dict[str, Any]:
    return s.view(s.create_handoff(db, values, actor, request))


@router.post("/handoffs/{identifier}/accept")
def accept_handoff(
    identifier: UUID, values: data.VersionInput, db: Database, actor: HandoffEdit, request: Request
) -> dict[str, Any]:
    return s.view(
        s.handoff_transition(db, _handoff(db, identifier, actor), "accept", values, actor, request)
    )


@router.post("/handoffs/{identifier}/complete")
def complete_handoff(
    identifier: UUID, values: data.VersionInput, db: Database, actor: HandoffEdit, request: Request
) -> dict[str, Any]:
    return s.view(
        s.handoff_transition(
            db, _handoff(db, identifier, actor), "complete", values, actor, request
        )
    )


@router.post("/handoffs/{identifier}/return")
def return_handoff(
    identifier: UUID, values: data.HandoffReturn, db: Database, actor: HandoffEdit, request: Request
) -> dict[str, Any]:
    return s.view(
        s.handoff_transition(
            db, _handoff(db, identifier, actor), "return", values, actor, request, values.reason
        )
    )


@router.get("/notifications")
def notifications(
    db: Database, actor: NotifyRead, limit: Limit = 50, cursor: str | None = None
) -> dict[str, Any]:
    page = page_query(
        select(Notification).where(
            Notification.recipient_user_id == actor.user.id, Notification.archived_at.is_(None)
        ),
        Notification,
        db,
        limit,
        cursor,
    )
    return {"items": [s.view(row) for row in page["rows"]], "next_cursor": page["next_cursor"]}


@router.post("/notifications/{identifier}/read")
def read_notification(
    identifier: UUID, values: data.VersionInput, db: Database, actor: NotifyRead
) -> dict[str, Any]:
    row = db.scalar(
        select(Notification).where(
            Notification.id == identifier,
            Notification.recipient_user_id == actor.user.id,
            Notification.archived_at.is_(None),
        )
    )
    if not row:
        raise ApiError(404, "NOTIFICATION_NOT_FOUND", "Notification not found.")
    writable(row, values.version)
    row.read_at = now()
    changed(row, actor.user.id)
    db.commit()
    return s.view(row)
