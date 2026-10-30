from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.core.errors import ApiError
from app.modules.demand.models import Organization
from app.modules.iam.dependencies import Database, Principal, require
from app.modules.iam.service import page_query
from app.modules.supply.ages import event_age, programme_today
from app.modules.supply.models import Participant, Person
from app.modules.training import schemas as data
from app.modules.training import service as s
from app.modules.training.models import Training, TrainingAttendance

router = APIRouter(tags=["training"])
Read = Annotated[Principal, Depends(require("training:view"))]
Edit = Annotated[Principal, Depends(require("training:view", "training:edit"))]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.get("/trainings")
def list_trainings(
    db: Database, actor: Read, limit: Limit = 25, cursor: str | None = None
) -> dict[str, Any]:
    page = page_query(
        select(Training).where(Training.archived_at.is_(None)), Training, db, limit, cursor
    )
    return {"items": [s.view(row) for row in page["rows"]], "next_cursor": page["next_cursor"]}


@router.post("/trainings", status_code=201)
def create_training(
    values: data.TrainingCreate, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    return s.view(s.create(db, values, actor, request))


@router.get("/trainings/{identifier}")
def training_detail(identifier: UUID, db: Database, actor: Read) -> dict[str, Any]:
    row = s.get(db, Training, identifier, "TRAINING_NOT_FOUND")
    result = s.view(row)
    result["attendance"] = [
        s.view(item)
        for item in db.scalars(
            select(TrainingAttendance).where(
                TrainingAttendance.training_id == row.id, TrainingAttendance.archived_at.is_(None)
            )
        )
    ]
    return result


@router.patch("/trainings/{identifier}")
def update_training(
    identifier: UUID, values: data.TrainingUpdate, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    return s.view(
        s.update(db, s.get(db, Training, identifier, "TRAINING_NOT_FOUND"), values, actor, request)
    )


@router.post("/trainings/{identifier}/participants", status_code=201)
def add_participants(
    identifier: UUID, values: data.AttendanceCreate, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    training = s.get(db, Training, identifier, "TRAINING_NOT_FOUND")
    return {
        "items": [s.view(row) for row in s.add_participants(db, training, values, actor, request)]
    }


@router.patch("/training-attendance/{identifier}")
def update_attendance(
    identifier: UUID, values: data.AttendanceUpdate, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    row = s.get(db, TrainingAttendance, identifier, "TRAINING_ATTENDANCE_NOT_FOUND")
    return s.view(s.update_attendance(db, row, values, actor, request))


@router.post("/training-attendance/{identifier}/certificate")
def issue_certificate(
    identifier: UUID, values: data.CertificateWrite, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    row = s.get(db, TrainingAttendance, identifier, "TRAINING_ATTENDANCE_NOT_FOUND")
    return s.view(s.issue_certificate(db, row, values, actor, request))


@router.get("/participants/{identifier}/capacity-building")
def participant_training(
    identifier: UUID, db: Database, actor: Read, limit: Limit = 25, cursor: str | None = None
) -> dict[str, Any]:
    if "participant:view" not in actor.permissions:
        raise ApiError(403, "PERMISSION_DENIED", "Participant access is required.")
    participant = s.get(db, Participant, identifier, "PARTICIPANT_NOT_FOUND")
    person = db.get(Person, participant.person_id)
    page = page_query(
        select(TrainingAttendance).where(
            TrainingAttendance.participant_id == identifier,
            TrainingAttendance.archived_at.is_(None),
        ),
        TrainingAttendance,
        db,
        limit,
        cursor,
    )
    items = []
    for row in page["rows"]:
        training = s.get(db, Training, row.training_id, "TRAINING_NOT_FOUND")
        partner = (
            db.get(Organization, training.partner_organization_id)
            if training.partner_organization_id
            else None
        )
        items.append(
            {
                **s.view(row),
                "training": {**s.view(training), "partner_name": partner.name if partner else None},
                "age_at_training_start": event_age(person.date_of_birth, training.start_date)
                if person and "participant_sensitive:view" in actor.permissions
                else None,
                "age_projected": training.start_date > programme_today(),
            }
        )
    return {"items": items, "next_cursor": page["next_cursor"]}
