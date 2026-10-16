from typing import Any, cast
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.modules.demand.models import Record
from app.modules.demand.service import changed, writable
from app.modules.iam.catalog import WORKSPACES
from app.modules.iam.dependencies import Principal
from app.modules.iam.models import User, now
from app.modules.iam.service import audit
from app.modules.work import schemas as data
from app.modules.work.models import Handoff, Notification, Task


def view(row: Record) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in cast(Any, row).__table__.columns}


def teams(actor: Principal) -> set[str]:
    return {code for code in WORKSPACES if f"workspace_{code.lower()}:view" in actor.permissions}


def task_scope(actor: Principal):
    allowed = teams(actor)
    return or_(
        Task.owner_user_id == actor.user.id,
        Task.created_by == actor.user.id,
        Task.owner_team.in_(allowed),
    )


def handoff_scope(actor: Principal):
    allowed = teams(actor)
    return or_(
        Handoff.sent_by == actor.user.id,
        Handoff.assigned_to == actor.user.id,
        Handoff.from_workstream.in_(allowed),
        Handoff.to_workstream.in_(allowed),
    )


def _user(db: Session, identifier: UUID | None) -> None:
    if identifier:
        row = db.get(User, identifier)
        if not row or not row.is_active:
            raise ApiError(404, "USER_NOT_FOUND", "Assigned user not found.")


def _team(code: str | None) -> None:
    if code and code not in WORKSPACES:
        raise ApiError(422, "UNKNOWN_WORKSTREAM", "Select a recognised workstream.")


def notify(
    db: Session,
    recipient: UUID | None,
    kind: str,
    title: str,
    body: str,
    entity_type: str,
    entity_id: UUID,
    actor: Principal,
) -> None:
    if recipient and recipient != actor.user.id:
        db.add(
            Notification(
                recipient_user_id=recipient,
                kind=kind,
                title=title,
                body=body,
                entity_type=entity_type,
                entity_id=entity_id,
                created_by=actor.user.id,
                updated_by=actor.user.id,
            )
        )


def create_task(db: Session, values: data.TaskCreate, actor: Principal, request: Request) -> Task:
    _user(db, values.owner_user_id)
    _team(values.owner_team)
    row = Task(
        task_code="TSK-" + uuid4().hex.upper(),
        **values.model_dump(),
        created_by=actor.user.id,
        updated_by=actor.user.id,
    )
    db.add(row)
    db.flush()
    notify(
        db, row.owner_user_id, "TASK_ASSIGNED", "Task assigned", row.title, "TASK", row.id, actor
    )
    audit(db, "task.created", actor.audit_actor, "task", row.id, request)
    db.commit()
    return row


def update_task(
    db: Session, row: Task, values: data.TaskUpdate, actor: Principal, request: Request
) -> Task:
    writable(row, values.version)
    _user(db, values.owner_user_id)
    _team(values.owner_team)
    previous_owner = row.owner_user_id
    for key, value in values.model_dump(exclude={"version"}).items():
        setattr(row, key, value)
    row.completed_at = now() if row.status == "COMPLETED" else None
    changed(row, actor.user.id)
    if row.owner_user_id != previous_owner:
        notify(
            db,
            row.owner_user_id,
            "TASK_ASSIGNED",
            "Task assigned",
            row.title,
            "TASK",
            row.id,
            actor,
        )
    audit(
        db,
        "task.updated",
        actor.audit_actor,
        "task",
        row.id,
        request,
        changes={"status": row.status},
    )
    db.commit()
    return row


def task_transition(
    db: Session, row: Task, status: str, version: int, actor: Principal, request: Request
) -> Task:
    writable(row, version)
    allowed = {
        "claim": ({"OPEN", "BLOCKED"}, "IN_PROGRESS"),
        "complete": ({"OPEN", "IN_PROGRESS", "BLOCKED"}, "COMPLETED"),
    }
    current, target = allowed[status]
    if row.status not in current:
        raise ApiError(409, "INVALID_TASK_TRANSITION", "The task cannot make that transition.")
    if status == "claim":
        row.owner_user_id = actor.user.id
    row.status = target
    row.completed_at = now() if target == "COMPLETED" else None
    changed(row, actor.user.id)
    audit(db, f"task.{status}ed", actor.audit_actor, "task", row.id, request)
    db.commit()
    return row


def create_handoff(
    db: Session, values: data.HandoffCreate, actor: Principal, request: Request
) -> Handoff:
    _team(values.from_workstream)
    _team(values.to_workstream)
    _user(db, values.assigned_to)
    if values.from_workstream == values.to_workstream:
        raise ApiError(422, "INVALID_HANDOFF", "A handoff must cross workstreams.")
    if values.from_workstream not in teams(actor):
        raise ApiError(403, "PERMISSION_DENIED", "You cannot send from that workstream.")
    row = Handoff(
        **values.model_dump(),
        status="SENT",
        sent_by=actor.user.id,
        sent_at=now(),
        created_by=actor.user.id,
        updated_by=actor.user.id,
    )
    db.add(row)
    db.flush()
    notify(
        db,
        row.assigned_to,
        "HANDOFF_SENT",
        "Handoff received",
        row.reason,
        "HANDOFF",
        row.id,
        actor,
    )
    audit(db, "handoff.sent", actor.audit_actor, "handoff", row.id, request)
    db.commit()
    return row


def handoff_transition(
    db: Session,
    row: Handoff,
    action: str,
    values: data.VersionInput,
    actor: Principal,
    request: Request,
    reason: str | None = None,
) -> Handoff:
    writable(row, values.version)
    transitions = {
        "accept": ({"SENT"}, "ACCEPTED"),
        "complete": ({"ACCEPTED", "IN_PROGRESS"}, "COMPLETED"),
        "return": ({"SENT", "ACCEPTED", "IN_PROGRESS"}, "RETURNED"),
    }
    sources, target = transitions[action]
    if row.status not in sources:
        raise ApiError(
            409, "INVALID_HANDOFF_TRANSITION", "The handoff cannot make that transition."
        )
    row.status = target
    if action == "accept":
        row.assigned_to = actor.user.id
        row.accepted_at = now()
    elif action == "complete":
        row.completed_at = now()
    else:
        row.return_reason = reason
    changed(row, actor.user.id)
    audit(db, f"handoff.{action}ed", actor.audit_actor, "handoff", row.id, request)
    db.commit()
    return row
