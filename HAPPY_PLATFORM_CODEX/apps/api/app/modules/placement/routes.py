from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.modules.demand.service import changed, get_record
from app.modules.iam.dependencies import Database, Principal, require
from app.modules.iam.service import page_query
from app.modules.placement import schemas as data
from app.modules.placement import service as s
from app.modules.placement.models import (
    EmploymentStatusHistory,
    FirstIncomeVerification,
    Placement,
    PlacementHistory,
)

router = APIRouter(tags=["placement"])
Read = Annotated[Principal, Depends(require("placement:view"))]
ParticipantRead = Annotated[Principal, Depends(require("placement:view", "participant:view"))]
Edit = Annotated[Principal, Depends(require("placement:view", "placement:edit"))]
IncomeRead = Annotated[Principal, Depends(require("placement:view", "first_income:view"))]
IncomeEdit = Annotated[
    Principal,
    Depends(require("placement:view", "first_income:view", "first_income:edit")),
]
Confirm = Annotated[
    Principal,
    Depends(
        require(
            "placement:view",
            "placement:edit",
            "first_income:view",
            "first_income:edit",
            "placement:confirm",
        )
    ),
]
Correct = Annotated[Principal, Depends(require("placement:correct_confirmation"))]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.get("/placements")
def placements(
    db: Database,
    actor: Read,
    status: str | None = None,
    participant_id: UUID | None = None,
    owner_id: UUID | None = None,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    query = select(Placement).where(Placement.archived_at.is_(None))
    if status:
        query = query.where(Placement.status == status)
    if participant_id:
        query = query.where(Placement.participant_id == participant_id)
    if owner_id:
        query = query.where(Placement.owner_id == owner_id)
    result = page_query(query, Placement, db, limit, cursor)
    return {
        "items": [s.placement_view(db, row, actor.permissions) for row in result["rows"]],
        "next_cursor": result["next_cursor"],
    }


@router.post("/placements", status_code=201)
def create(
    values: data.PlacementCreate, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    return s.placement_view(db, s.create(db, values, actor, request), actor.permissions)


@router.get("/participants/{identifier}/placements")
def participant_placements(
    identifier: UUID,
    db: Database,
    actor: ParticipantRead,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    result = page_query(
        select(Placement).where(
            Placement.participant_id == identifier, Placement.archived_at.is_(None)
        ),
        Placement,
        db,
        limit,
        cursor,
    )
    return {
        "items": [s.placement_view(db, row, actor.permissions) for row in result["rows"]],
        "next_cursor": result["next_cursor"],
    }


@router.get("/placements/{identifier}")
def detail(identifier: UUID, db: Database, actor: Read) -> dict[str, Any]:
    return s.placement_view(db, get_record(db, Placement, identifier), actor.permissions)


@router.patch("/placements/{identifier}")
def patch(
    identifier: UUID,
    values: data.PlacementPatch,
    db: Database,
    actor: Edit,
    request: Request,
) -> dict[str, Any]:
    row = s.locked(db, identifier, values.version)
    if row.status not in {"START_PENDING", "STARTED", "AWAITING_FIRST_INCOME"}:
        from app.modules.demand.service import fail

        fail("PLACEMENT_CLOSED", "Confirmed or ended placements need privileged correction.", 422)
    for key, value in values.model_dump(
        exclude={"version", "reason", "manual_first_income_date", "exception_reason"}
    ).items():
        setattr(row, key, value)
    first = s.verification(db, row.id, lock=True)
    if values.manual_first_income_date:
        first.verification_due_date = values.manual_first_income_date
        first.status = "EXCEPTION"
        first.exception_reason = values.exception_reason or values.reason
        row.expected_first_income_date = values.manual_first_income_date
        changed(first, actor.user.id)
    changed(row, actor.user.id)
    s.save(db, row, actor, request, "placement.updated", ["details"])
    return s.placement_view(db, row, actor.permissions)


@router.post("/placements/{identifier}/confirm-start")
def start(
    identifier: UUID, values: data.Start, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    return s.placement_view(
        db, s.confirm_start(db, identifier, values, actor, request), actor.permissions
    )


@router.patch("/placements/{identifier}/programme-details")
def programme_details(
    identifier: UUID,
    values: data.PlacementDetailsWrite,
    db: Database,
    actor: Edit,
    request: Request,
) -> dict[str, Any]:
    from app.core.errors import ApiError

    row = s.locked(db, identifier, values.version)
    if row.confirmed_at and "placement:correct_confirmation" not in actor.permissions:
        raise ApiError(
            403, "PERMISSION_DENIED", "Confirmed placement corrections require elevated permission."
        )
    for key, value in values.model_dump(exclude={"version", "reason"}).items():
        setattr(row, key, value)
    from app.modules.iam.service import audit

    audit(
        db,
        "placement.updated",
        actor.audit_actor,
        "PLACEMENT",
        row.id,
        request,
        changes={"reason": values.reason, "section": "programme_details"},
    )
    changed(row, actor.user.id)
    db.commit()
    db.refresh(row)
    return s.placement_view(db, row, actor.permissions)


@router.post("/placements/{identifier}/start-outcome")
def start_outcome(
    identifier: UUID,
    values: data.StartOutcome,
    db: Database,
    actor: Edit,
    request: Request,
) -> dict[str, Any]:
    return s.placement_view(
        db, s.start_outcome(db, identifier, values, actor, request), actor.permissions
    )


@router.post("/placements/{identifier}/employment-end")
def employment_end(
    identifier: UUID, values: data.End, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    return s.placement_view(db, s.end(db, identifier, values, actor, request), actor.permissions)


@router.get("/placements/{identifier}/first-income")
def first_income(identifier: UUID, db: Database, actor: IncomeRead) -> dict[str, Any]:
    get_record(db, Placement, identifier)
    row = s.verification(db, identifier)
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "version",
            "status",
            "verification_due_date",
            "actual_income_received_date",
            "verified_at",
            "verified_by",
            "amount_received",
            "evidence_document_id",
            "exception_reason",
            "notes",
        )
    }


@router.post("/placements/{identifier}/first-income/confirm")
def confirm(
    identifier: UUID,
    values: data.FirstIncomeConfirm,
    db: Database,
    actor: Confirm,
    request: Request,
) -> dict[str, Any]:
    return s.placement_view(
        db, s.confirm_income(db, identifier, values, actor, request), actor.permissions
    )


def _reschedule(
    identifier: UUID,
    values: data.FirstIncomeDelay,
    db: Database,
    actor: Principal,
    request: Request,
    status: str,
) -> dict[str, Any]:
    get_record(db, Placement, identifier)
    row = s.verification(db, identifier, lock=True)
    from app.modules.demand.service import writable

    writable(row, values.version)
    row.verification_due_date = values.verification_due_date
    row.status = status
    row.exception_reason = values.reason
    changed(row, actor.user.id)
    placement = get_record(db, Placement, identifier)
    placement.expected_first_income_date = values.verification_due_date
    changed(placement, actor.user.id)
    s.save(db, placement, actor, request, f"placement.first_income.{status.lower()}", ["due"])
    return s.placement_view(db, placement, actor.permissions)


@router.post("/placements/{identifier}/first-income/delay")
def delay(
    identifier: UUID,
    values: data.FirstIncomeDelay,
    db: Database,
    actor: IncomeEdit,
    request: Request,
) -> dict[str, Any]:
    return _reschedule(identifier, values, db, actor, request, "PAYMENT_DELAYED")


@router.post("/placements/{identifier}/first-income/exception")
def exception(
    identifier: UUID,
    values: data.FirstIncomeException,
    db: Database,
    actor: IncomeEdit,
    request: Request,
) -> dict[str, Any]:
    return _reschedule(identifier, values, db, actor, request, "EXCEPTION")


@router.post("/placements/{identifier}/correct-confirmation")
def correct_confirmation(
    identifier: UUID,
    values: data.CorrectConfirmation,
    db: Database,
    actor: Correct,
    request: Request,
) -> dict[str, Any]:
    return s.placement_view(
        db,
        s.correct_confirmation(db, identifier, values, actor, request),
        actor.permissions,
    )


@router.get("/placements/{identifier}/history")
def history(
    identifier: UUID, db: Database, actor: Read, limit: Limit = 25, cursor: str | None = None
) -> dict[str, Any]:
    get_record(db, Placement, identifier)
    result = page_query(
        select(PlacementHistory).where(PlacementHistory.placement_id == identifier),
        PlacementHistory,
        db,
        limit,
        cursor,
    )
    return {
        "items": [
            {
                key: getattr(row, key)
                for key in (
                    "id",
                    "from_status",
                    "to_status",
                    "reason",
                    "actor_type",
                    "actor_id",
                    "occurred_at",
                )
            }
            for row in result["rows"]
        ],
        "next_cursor": result["next_cursor"],
    }


@router.get("/placements/{identifier}/employment-history")
def employment_history(
    identifier: UUID, db: Database, actor: Read, limit: Limit = 25, cursor: str | None = None
) -> dict[str, Any]:
    get_record(db, Placement, identifier)
    result = page_query(
        select(EmploymentStatusHistory).where(EmploymentStatusHistory.placement_id == identifier),
        EmploymentStatusHistory,
        db,
        limit,
        cursor,
    )
    return {
        "items": [
            {key: getattr(row, key) for key in ("id", "status", "effective_date", "notes")}
            for row in result["rows"]
        ],
        "next_cursor": result["next_cursor"],
    }


@router.get("/first-income/queue")
def queue(
    db: Database,
    actor: IncomeRead,
    bucket: str | None = None,
    limit: Limit = 100,
) -> dict[str, Any]:
    rows = list(
        db.scalars(
            select(Placement)
            .join(FirstIncomeVerification, FirstIncomeVerification.placement_id == Placement.id)
            .where(
                Placement.archived_at.is_(None),
                Placement.status == "AWAITING_FIRST_INCOME",
            )
            .order_by(FirstIncomeVerification.verification_due_date, Placement.id)
            .limit(limit)
        )
    )
    items = [s.placement_view(db, row, actor.permissions) for row in rows]
    if bucket:
        items = [row for row in items if row["first_income"]["status"] == bucket]
    return {"items": items, "next_cursor": None, "as_of": date.today()}
