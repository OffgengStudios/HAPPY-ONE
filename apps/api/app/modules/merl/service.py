from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, NoReturn
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.modules.demand.service import assignable, changed, writable
from app.modules.iam.dependencies import Principal
from app.modules.iam.models import now
from app.modules.iam.service import audit
from app.modules.merl import schemas as data
from app.modules.merl.models import (
    DataQualityIssue,
    FollowUp,
    FollowUpTemplate,
    Outcome,
    OutcomeRevision,
)
from app.modules.placement.models import EmploymentStatusHistory, Placement
from app.modules.supply.models import Participant, Person


def fail(code: str, message: str, status: int = 409) -> NoReturn:
    raise ApiError(status, code, message)


def refresh_status(row: FollowUp, today: date | None = None) -> None:
    if row.status not in {"SCHEDULED", "DUE", "OVERDUE"}:
        return
    current = today or now().date()
    row.status = (
        "OVERDUE"
        if row.scheduled_for < current
        else "DUE"
        if row.scheduled_for == current
        else "SCHEDULED"
    )


def follow_up_view(db: Session, row: FollowUp) -> dict[str, Any]:
    refresh_status(row)
    person = db.scalar(
        select(Person)
        .join(Participant, Participant.person_id == Person.id)
        .where(Participant.id == row.participant_id)
    )
    return {
        "id": row.id,
        "version": row.version,
        "follow_up_code": row.follow_up_code,
        "participant_id": row.participant_id,
        "participant_name": " ".join(
            filter(None, [person.first_name, person.other_names, person.surname])
        )
        if person
        else "Unknown participant",
        "placement_id": row.placement_id,
        "template_id": row.template_id,
        "follow_up_type": row.follow_up_type,
        "scheduled_for": row.scheduled_for,
        "status": row.status,
        "owner_id": row.owner_id,
        "completed_at": row.completed_at,
        "completed_by": row.completed_by,
        "contact_result": row.contact_result,
        "notes": row.notes,
        "created_at": row.created_at,
    }


OUTCOME_FIELDS = tuple(data.OutcomeFields.model_fields)


def outcome_view(db: Session, row: Outcome, permissions: set[str]) -> dict[str, Any]:
    person = db.scalar(
        select(Person)
        .join(Participant, Participant.person_id == Person.id)
        .where(Participant.id == row.participant_id)
    )
    result = {
        "id": row.id,
        "version": row.version,
        "participant_id": row.participant_id,
        "participant_name": " ".join(
            filter(None, [person.first_name, person.other_names, person.surname])
        )
        if person
        else "Unknown participant",
        "placement_id": row.placement_id,
        "follow_up_id": row.follow_up_id,
        "verified_by": row.verified_by,
        "created_at": row.created_at,
        **{field: getattr(row, field) for field in OUTCOME_FIELDS},
    }
    if "participant_sensitive:view" not in permissions:
        result.pop("current_income_amount", None)
        result.pop("income_frequency", None)
    return result


def issue_view(row: DataQualityIssue) -> dict[str, Any]:
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "version",
            "issue_code",
            "entity_type",
            "entity_id",
            "issue_type",
            "severity",
            "status",
            "description",
            "owner_id",
            "detected_at",
            "resolved_at",
            "resolved_by",
            "resolution_notes",
            "created_at",
            "updated_at",
        )
    }


def get_placement(db: Session, identifier: UUID) -> Placement:
    row = db.get(Placement, identifier)
    if not row or row.archived_at:
        fail("PLACEMENT_NOT_FOUND", "Placement not found.", 404)
    return row


def schedule(
    db: Session, values: data.FollowUpCreate, actor: Principal, request: Request
) -> FollowUp:
    placement = get_placement(db, values.placement_id)
    if not placement.actual_start_date or placement.status in {"FAILED_TO_START", "CANCELLED"}:
        fail("PLACEMENT_NOT_STARTED", "Follow-up requires an actual placement start.")
    scheduled = values.scheduled_for
    template = None
    if values.template_id:
        template = db.get(FollowUpTemplate, values.template_id)
        if not template or template.archived_at or not template.is_active:
            fail("FOLLOW_UP_TEMPLATE_NOT_FOUND", "Active follow-up template not found.", 404)
        anchor = placement.actual_start_date
        if template.anchor == "CONFIRMED":
            if not placement.confirmed_at:
                fail("PLACEMENT_NOT_CONFIRMED", "This template requires a confirmed placement.")
            anchor = placement.confirmed_at.date()
        scheduled = anchor + timedelta(days=template.offset_days)
    assert scheduled
    if scheduled < placement.actual_start_date:
        fail("FOLLOW_UP_BEFORE_START", "Follow-up cannot precede the actual start date.", 422)
    assignable(db, values.owner_id, "follow_up:edit")
    follow_up_type = template.follow_up_type if template else values.follow_up_type
    assert follow_up_type
    row = FollowUp(
        follow_up_code="FUP-" + uuid4().hex.upper(),
        participant_id=placement.participant_id,
        placement_id=placement.id,
        template_id=template.id if template else None,
        follow_up_type=follow_up_type,
        scheduled_for=scheduled,
        owner_id=values.owner_id,
        created_by=actor.user.id,
        updated_by=actor.user.id,
    )
    refresh_status(row)
    db.add(row)
    db.flush()
    audit(db, "follow_up.created", actor.audit_actor, "follow_up", row.id, request)
    db.commit()
    return row


def complete(
    db: Session,
    row: FollowUp,
    values: data.FollowUpComplete,
    actor: Principal,
    request: Request,
) -> FollowUp:
    writable(row, values.version)
    if row.status in {"COMPLETED", "CANCELLED"}:
        fail("FOLLOW_UP_CLOSED", "This follow-up is already closed.")
    row.status = "COMPLETED"
    row.completed_at = now()
    row.completed_by = actor.user.id
    row.contact_result = values.contact_result
    row.notes = values.notes
    changed(row, actor.user.id)
    audit(db, "follow_up.completed", actor.audit_actor, "follow_up", row.id, request)
    db.commit()
    return row


def _validate_outcome(
    db: Session, placement: Placement, as_of: date, follow_up_id: UUID | None
) -> FollowUp | None:
    if not placement.actual_start_date or as_of < placement.actual_start_date:
        fail("OUTCOME_BEFORE_START", "Outcome date cannot precede actual placement start.", 422)
    if as_of > now().date():
        fail("OUTCOME_IN_FUTURE", "Outcome date cannot be in the future.", 422)
    follow_up = db.get(FollowUp, follow_up_id) if follow_up_id else None
    if follow_up_id and (
        not follow_up or follow_up.placement_id != placement.id or follow_up.status != "COMPLETED"
    ):
        fail("INVALID_FOLLOW_UP", "Choose a completed follow-up for this placement.", 422)
    return follow_up


def _outcome_values(values: data.OutcomeFields) -> dict[str, Any]:
    return {field: getattr(values, field) for field in OUTCOME_FIELDS}


def record_outcome(
    db: Session, values: data.OutcomeCreate, actor: Principal, request: Request
) -> Outcome:
    placement = get_placement(db, values.placement_id)
    _validate_outcome(db, placement, values.as_of_date, values.follow_up_id)
    if values.follow_up_id and db.scalar(
        select(Outcome.id).where(Outcome.follow_up_id == values.follow_up_id)
    ):
        fail("FOLLOW_UP_OUTCOME_EXISTS", "This follow-up already has an outcome.")
    if (
        values.current_income_amount is not None
        and "participant_sensitive:edit" not in actor.permissions
    ):
        fail("PERMISSION_DENIED", "Sensitive income recording is not permitted.", 403)
    row = Outcome(
        participant_id=placement.participant_id,
        placement_id=placement.id,
        follow_up_id=values.follow_up_id,
        verified_by=actor.user.id,
        created_by=actor.user.id,
        updated_by=actor.user.id,
        **_outcome_values(values),
    )
    db.add(row)
    db.flush()
    db.add(
        EmploymentStatusHistory(
            placement_id=placement.id,
            status="WORKING" if row.currently_working else "ENDED",
            effective_date=row.as_of_date,
            source="MERL_OUTCOME",
            verified_by=actor.user.id,
            notes="Verified M&E outcome " + str(row.id),
        )
    )
    if (
        placement.employment_end_date
        and row.currently_working
        and row.as_of_date >= placement.employment_end_date
    ):
        create_issue(
            db,
            data.IssueCreate(
                entity_type="OUTCOME",
                entity_id=row.id,
                issue_type="EMPLOYMENT_STATE_CONFLICT",
                severity="HIGH",
                description="Outcome reports working after this placement was recorded as ended.",
            ),
            actor,
            request,
            commit=False,
        )
    audit(db, "outcome.created", actor.audit_actor, "outcome", row.id, request)
    db.commit()
    return row


def snapshot(row: Outcome) -> dict[str, Any]:
    def json_value(value: Any) -> Any:
        if isinstance(value, (date, datetime, Decimal, UUID)):
            return str(value)
        return value

    return {
        **{field: json_value(getattr(row, field)) for field in OUTCOME_FIELDS},
        "follow_up_id": str(row.follow_up_id) if row.follow_up_id else None,
    }


def correct_outcome(
    db: Session,
    row: Outcome,
    values: data.OutcomeUpdate,
    actor: Principal,
    request: Request,
) -> Outcome:
    writable(row, values.version)
    placement = get_placement(db, row.placement_id)
    _validate_outcome(db, placement, values.as_of_date, row.follow_up_id)
    if (
        values.current_income_amount is not None
        and "participant_sensitive:edit" not in actor.permissions
    ):
        fail("PERMISSION_DENIED", "Sensitive income recording is not permitted.", 403)
    db.add(
        OutcomeRevision(
            outcome_id=row.id,
            previous_json=snapshot(row),
            reason=values.reason,
            corrected_by=actor.user.id,
        )
    )
    for key, value in _outcome_values(values).items():
        setattr(row, key, value)
    row.verified_by = actor.user.id
    changed(row, actor.user.id)
    db.add(
        EmploymentStatusHistory(
            placement_id=placement.id,
            status="WORKING" if row.currently_working else "ENDED",
            effective_date=row.as_of_date,
            source="MERL_CORRECTION",
            verified_by=actor.user.id,
            notes="Corrected M&E outcome " + str(row.id),
        )
    )
    audit(
        db,
        "outcome.updated",
        actor.audit_actor,
        "outcome",
        row.id,
        request,
        changes={"reason": values.reason},
    )
    db.commit()
    return row


def create_issue(
    db: Session,
    values: data.IssueCreate,
    actor: Principal,
    request: Request,
    *,
    commit: bool = True,
) -> DataQualityIssue:
    entity_models = {
        "PARTICIPANT": Participant,
        "PLACEMENT": Placement,
        "FOLLOW_UP": FollowUp,
        "OUTCOME": Outcome,
    }
    entity = db.get(entity_models[values.entity_type], values.entity_id)
    if not entity or getattr(entity, "archived_at", None):
        fail("DATA_QUALITY_ENTITY_NOT_FOUND", "Referenced record not found.", 404)
    row = DataQualityIssue(
        issue_code="DQI-" + uuid4().hex.upper(),
        created_by=actor.user.id,
        updated_by=actor.user.id,
        **values.model_dump(),
    )
    db.add(row)
    db.flush()
    audit(db, "data_quality.created", actor.audit_actor, "data_quality_issue", row.id, request)
    if commit:
        db.commit()
    return row


def dashboard(db: Session) -> dict[str, Any]:
    today = now().date()
    open_status = ["SCHEDULED", "DUE", "OVERDUE"]
    followups = list(db.scalars(select(FollowUp).where(FollowUp.status.in_(open_status))))
    for row in followups:
        refresh_status(row, today)
    db.flush()
    ranked = (
        select(
            Outcome.currently_working,
            func.row_number()
            .over(
                partition_by=Outcome.placement_id,
                order_by=(Outcome.as_of_date.desc(), Outcome.created_at.desc(), Outcome.id.desc()),
            )
            .label("rank"),
        )
        .where(Outcome.archived_at.is_(None))
        .subquery()
    )
    working = (
        db.scalar(
            select(func.count())
            .select_from(ranked)
            .where(ranked.c.rank == 1, ranked.c.currently_working.is_(True))
        )
        or 0
    )
    return {
        "scheduled": sum(row.status == "SCHEDULED" for row in followups),
        "due": sum(row.status == "DUE" for row in followups),
        "overdue": sum(row.status == "OVERDUE" for row in followups),
        "completed": db.scalar(
            select(func.count()).select_from(FollowUp).where(FollowUp.status == "COMPLETED")
        )
        or 0,
        "latest_verified_working": working,
        "impact_story_candidates": db.scalar(
            select(func.count())
            .select_from(Outcome)
            .where(Outcome.impact_story_potential.is_(True), Outcome.archived_at.is_(None))
        )
        or 0,
        "open_data_quality": db.scalar(
            select(func.count())
            .select_from(DataQualityIssue)
            .where(DataQualityIssue.status.in_(["OPEN", "IN_PROGRESS"]))
        )
        or 0,
    }
