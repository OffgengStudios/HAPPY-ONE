from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.core.errors import ApiError
from app.modules.demand.service import assignable, changed, writable
from app.modules.iam.dependencies import Database, Principal, require
from app.modules.iam.models import now
from app.modules.iam.service import audit, page_query
from app.modules.merl import schemas as data
from app.modules.merl import service as s
from app.modules.merl.models import DataQualityIssue, FollowUp, FollowUpTemplate, Outcome

router = APIRouter(tags=["merl"])
FollowRead = Annotated[Principal, Depends(require("follow_up:view"))]
FollowEdit = Annotated[Principal, Depends(require("follow_up:view", "follow_up:edit"))]
OutcomeRead = Annotated[Principal, Depends(require("outcome:view"))]
OutcomeEdit = Annotated[Principal, Depends(require("outcome:view", "outcome:edit"))]
QualityRead = Annotated[Principal, Depends(require("data_quality:view"))]
QualityEdit = Annotated[Principal, Depends(require("data_quality:view", "data_quality:edit"))]
Configure = Annotated[Principal, Depends(require("follow_up:configure"))]
Limit = Annotated[int, Query(ge=1, le=100)]


def get(db: Database, model: type[Any], identifier: UUID, code: str) -> Any:
    row = db.get(model, identifier)
    if not row or getattr(row, "archived_at", None):
        raise ApiError(404, code, "Record not found.")
    return row


@router.get("/merl/dashboard")
def merl_dashboard(db: Database, actor: FollowRead) -> dict[str, Any]:
    return s.dashboard(db)


@router.get("/follow-ups")
def follow_ups(
    db: Database,
    actor: FollowRead,
    status: str | None = None,
    placement_id: UUID | None = None,
    owner_id: UUID | None = None,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    query = select(FollowUp).where(FollowUp.archived_at.is_(None))
    today = now().date()
    if status == "SCHEDULED":
        query = query.where(
            FollowUp.status.in_(["SCHEDULED", "DUE", "OVERDUE"]),
            FollowUp.scheduled_for > today,
        )
    elif status == "DUE":
        query = query.where(
            FollowUp.status.in_(["SCHEDULED", "DUE", "OVERDUE"]),
            FollowUp.scheduled_for == today,
        )
    elif status == "OVERDUE":
        query = query.where(
            FollowUp.status.in_(["SCHEDULED", "DUE", "OVERDUE"]),
            FollowUp.scheduled_for < today,
        )
    elif status:
        query = query.where(FollowUp.status == status)
    if placement_id:
        query = query.where(FollowUp.placement_id == placement_id)
    if owner_id:
        query = query.where(FollowUp.owner_id == owner_id)
    page = page_query(query, FollowUp, db, limit, cursor)
    return {
        "items": [s.follow_up_view(db, row) for row in page["rows"]],
        "next_cursor": page["next_cursor"],
    }


@router.post("/follow-ups", status_code=201)
def follow_up_create(
    values: data.FollowUpCreate, db: Database, actor: FollowEdit, request: Request
) -> dict[str, Any]:
    return s.follow_up_view(db, s.schedule(db, values, actor, request))


@router.get("/follow-ups/{identifier}")
def follow_up_detail(identifier: UUID, db: Database, actor: FollowRead) -> dict[str, Any]:
    return s.follow_up_view(db, get(db, FollowUp, identifier, "FOLLOW_UP_NOT_FOUND"))


@router.post("/follow-ups/{identifier}/complete")
def follow_up_complete(
    identifier: UUID,
    values: data.FollowUpComplete,
    db: Database,
    actor: FollowEdit,
    request: Request,
) -> dict[str, Any]:
    row = get(db, FollowUp, identifier, "FOLLOW_UP_NOT_FOUND")
    return s.follow_up_view(db, s.complete(db, row, values, actor, request))


@router.post("/follow-ups/{identifier}/cancel")
def follow_up_cancel(
    identifier: UUID,
    values: data.FollowUpCancel,
    db: Database,
    actor: FollowEdit,
    request: Request,
) -> dict[str, Any]:
    row = get(db, FollowUp, identifier, "FOLLOW_UP_NOT_FOUND")
    writable(row, values.version)
    if row.status in {"COMPLETED", "CANCELLED"}:
        raise ApiError(409, "FOLLOW_UP_CLOSED", "This follow-up is already closed.")
    row.status = "CANCELLED"
    row.notes = values.reason
    changed(row, actor.user.id)
    audit(db, "follow_up.cancelled", actor.audit_actor, "follow_up", row.id, request)
    db.commit()
    return s.follow_up_view(db, row)


@router.get("/outcomes")
def outcomes(
    db: Database,
    actor: OutcomeRead,
    placement_id: UUID | None = None,
    impact_story_potential: bool | None = None,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    query = select(Outcome).where(Outcome.archived_at.is_(None))
    if placement_id:
        query = query.where(Outcome.placement_id == placement_id)
    if impact_story_potential is not None:
        query = query.where(Outcome.impact_story_potential == impact_story_potential)
    page = page_query(query, Outcome, db, limit, cursor)
    return {
        "items": [s.outcome_view(db, row, actor.permissions) for row in page["rows"]],
        "next_cursor": page["next_cursor"],
    }


@router.post("/outcomes", status_code=201)
def outcome_create(
    values: data.OutcomeCreate, db: Database, actor: OutcomeEdit, request: Request
) -> dict[str, Any]:
    return s.outcome_view(db, s.record_outcome(db, values, actor, request), actor.permissions)


@router.get("/outcomes/{identifier}")
def outcome_detail(identifier: UUID, db: Database, actor: OutcomeRead) -> dict[str, Any]:
    return s.outcome_view(db, get(db, Outcome, identifier, "OUTCOME_NOT_FOUND"), actor.permissions)


@router.patch("/outcomes/{identifier}")
def outcome_update(
    identifier: UUID,
    values: data.OutcomeUpdate,
    db: Database,
    actor: OutcomeEdit,
    request: Request,
) -> dict[str, Any]:
    row = get(db, Outcome, identifier, "OUTCOME_NOT_FOUND")
    return s.outcome_view(db, s.correct_outcome(db, row, values, actor, request), actor.permissions)


@router.get("/data-quality/issues")
def issues(
    db: Database,
    actor: QualityRead,
    status: str | None = None,
    severity: str | None = None,
    owner_id: UUID | None = None,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    query = select(DataQualityIssue).where(DataQualityIssue.archived_at.is_(None))
    if status:
        query = query.where(DataQualityIssue.status == status)
    if severity:
        query = query.where(DataQualityIssue.severity == severity)
    if owner_id:
        query = query.where(DataQualityIssue.owner_id == owner_id)
    page = page_query(query, DataQualityIssue, db, limit, cursor)
    return {
        "items": [s.issue_view(row) for row in page["rows"]],
        "next_cursor": page["next_cursor"],
    }


@router.post("/data-quality/issues", status_code=201)
def issue_create(
    values: data.IssueCreate, db: Database, actor: QualityEdit, request: Request
) -> dict[str, Any]:
    return s.issue_view(s.create_issue(db, values, actor, request))


@router.post("/data-quality/issues/{identifier}/assign")
def issue_assign(
    identifier: UUID,
    values: data.IssueAssign,
    db: Database,
    actor: QualityEdit,
    request: Request,
) -> dict[str, Any]:
    row = get(db, DataQualityIssue, identifier, "DATA_QUALITY_ISSUE_NOT_FOUND")
    writable(row, values.version)
    assignable(db, values.owner_id, "data_quality:edit")
    row.owner_id = values.owner_id
    row.status = "IN_PROGRESS"
    changed(row, actor.user.id)
    audit(db, "data_quality.assigned", actor.audit_actor, "data_quality_issue", row.id, request)
    db.commit()
    return s.issue_view(row)


@router.post("/data-quality/issues/{identifier}/resolve")
def issue_resolve(
    identifier: UUID,
    values: data.IssueResolve,
    db: Database,
    actor: QualityEdit,
    request: Request,
) -> dict[str, Any]:
    row = get(db, DataQualityIssue, identifier, "DATA_QUALITY_ISSUE_NOT_FOUND")
    writable(row, values.version)
    if row.status in {"RESOLVED", "DISMISSED"}:
        raise ApiError(409, "DATA_QUALITY_ISSUE_CLOSED", "This issue is already closed.")
    row.status = values.resolution
    row.resolved_at = now()
    row.resolved_by = actor.user.id
    row.resolution_notes = values.notes
    changed(row, actor.user.id)
    audit(db, "data_quality.resolved", actor.audit_actor, "data_quality_issue", row.id, request)
    db.commit()
    return s.issue_view(row)


@router.get("/follow-up-templates")
def templates(db: Database, actor: FollowRead) -> dict[str, Any]:
    rows = db.scalars(
        select(FollowUpTemplate)
        .where(FollowUpTemplate.archived_at.is_(None))
        .order_by(FollowUpTemplate.name)
    )
    return {"items": [template_view(row) for row in rows]}


def template_view(row: FollowUpTemplate) -> dict[str, Any]:
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "version",
            "template_code",
            "name",
            "follow_up_type",
            "anchor",
            "offset_days",
            "required_questions",
            "owner_role_code",
            "is_active",
        )
    }


@router.post("/follow-up-templates", status_code=201)
def template_create(
    values: data.TemplateWrite, db: Database, actor: Configure, request: Request
) -> dict[str, Any]:
    row = FollowUpTemplate(
        **values.model_dump(), created_by=actor.user.id, updated_by=actor.user.id
    )
    db.add(row)
    db.flush()
    audit(
        db, "follow_up_template.created", actor.audit_actor, "follow_up_template", row.id, request
    )
    db.commit()
    return template_view(row)


@router.patch("/follow-up-templates/{identifier}")
def template_update(
    identifier: UUID, values: data.TemplateUpdate, db: Database, actor: Configure, request: Request
) -> dict[str, Any]:
    row = get(db, FollowUpTemplate, identifier, "FOLLOW_UP_TEMPLATE_NOT_FOUND")
    writable(row, values.version)
    for key, value in values.model_dump(exclude={"version"}).items():
        setattr(row, key, value)
    changed(row, actor.user.id)
    audit(
        db, "follow_up_template.updated", actor.audit_actor, "follow_up_template", row.id, request
    )
    db.commit()
    return template_view(row)
