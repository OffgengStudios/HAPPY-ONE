from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.modules.iam.dependencies import Database, Principal, require
from app.modules.iam.service import page_query
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
