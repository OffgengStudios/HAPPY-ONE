from typing import Any, cast
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.modules.demand.models import Organization, Record
from app.modules.demand.service import changed, writable
from app.modules.iam.dependencies import Principal
from app.modules.iam.service import audit
from app.modules.supply.models import Document, Participant, Person
from app.modules.training import schemas as data
from app.modules.training.models import Training, TrainingAttendance


def get[T: Record](db: Session, model: type[T], identifier: UUID, code: str) -> T:
    row = db.get(model, identifier)
    if not row or row.archived_at:
        raise ApiError(404, code, "Record not found.")
    return row


def view(row: Record) -> dict[str, Any]:
    table = cast(Any, row).__table__
    return {column.name: getattr(row, column.name) for column in table.columns}


def validate_links(db: Session, values: data.TrainingFields) -> None:
    if values.partner_organization_id:
        organization = db.get(Organization, values.partner_organization_id)
        if not organization or organization.archived_at:
            raise ApiError(404, "ORGANIZATION_NOT_FOUND", "Partner organization not found.")


def create(
    db: Session, values: data.TrainingCreate, actor: Principal, request: Request
) -> Training:
    validate_links(db, values)
    row = Training(
        training_code="TRN-" + uuid4().hex.upper(),
        **values.model_dump(),
        created_by=actor.user.id,
        updated_by=actor.user.id,
    )
    db.add(row)
    db.flush()
    audit(db, "training.created", actor.audit_actor, "training", row.id, request)
    db.commit()
    return row


def update(
    db: Session, row: Training, values: data.TrainingUpdate, actor: Principal, request: Request
) -> Training:
    writable(row, values.version)
    validate_links(db, values)
    previous_dates = {
        "start_date": str(row.start_date),
        "end_date": str(row.end_date) if row.end_date else None,
    }
    if db.scalar(
        select(Person.id)
        .join(Participant, Participant.person_id == Person.id)
        .join(TrainingAttendance, TrainingAttendance.participant_id == Participant.id)
        .where(TrainingAttendance.training_id == row.id, Person.date_of_birth > values.start_date)
    ):
        raise ApiError(
            422, "EVENT_BEFORE_BIRTH", "Training cannot start before a participant's birth."
        )
    for key, value in values.model_dump(exclude={"version"}, exclude_unset=True).items():
        setattr(row, key, value)
    changed(row, actor.user.id)
    audit(
        db,
        "training.updated",
        actor.audit_actor,
        "training",
        row.id,
        request,
        changes={
            "previous_dates": previous_dates,
            "start_date": str(row.start_date),
            "end_date": str(row.end_date) if row.end_date else None,
        },
    )
    db.commit()
    return row


def add_participants(
    db: Session,
    training: Training,
    values: data.AttendanceCreate,
    actor: Principal,
    request: Request,
) -> list[TrainingAttendance]:
    unique_ids = list(dict.fromkeys(values.participant_ids))
    participants = set(
        db.scalars(
            select(Participant.id).where(
                Participant.id.in_(unique_ids), Participant.archived_at.is_(None)
            )
        )
    )
    if participants != set(unique_ids):
        raise ApiError(404, "PARTICIPANT_NOT_FOUND", "One or more participants were not found.")
    if db.scalar(
        select(Person.id)
        .join(Participant, Participant.person_id == Person.id)
        .where(Participant.id.in_(unique_ids), Person.date_of_birth > training.start_date)
    ):
        raise ApiError(
            422, "EVENT_BEFORE_BIRTH", "Training cannot start before a participant's birth."
        )
    rows = [
        TrainingAttendance(
            training_id=training.id,
            participant_id=identifier,
            attendance_status=values.attendance_status,
            completion_status=values.completion_status,
            notes=values.notes,
            created_by=actor.user.id,
            updated_by=actor.user.id,
        )
        for identifier in unique_ids
    ]
    db.add_all(rows)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise ApiError(
            409, "TRAINING_ATTENDANCE_EXISTS", "A participant is already enrolled."
        ) from error
    audit(
        db,
        "training.participants_added",
        actor.audit_actor,
        "training",
        training.id,
        request,
        changes={"count": len(rows)},
    )
    db.commit()
    return rows


def update_attendance(
    db: Session,
    row: TrainingAttendance,
    values: data.AttendanceUpdate,
    actor: Principal,
    request: Request,
) -> TrainingAttendance:
    writable(row, values.version)
    for key, value in values.model_dump(exclude={"version"}, exclude_unset=True).items():
        setattr(row, key, value)
    changed(row, actor.user.id)
    audit(
        db, "training_attendance.updated", actor.audit_actor, "training_attendance", row.id, request
    )
    db.commit()
    return row


def issue_certificate(
    db: Session,
    row: TrainingAttendance,
    values: data.CertificateWrite,
    actor: Principal,
    request: Request,
) -> TrainingAttendance:
    writable(row, values.version)
    document = db.get(Document, values.document_id)
    if not document or document.archived_at or document.participant_id != row.participant_id:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "Participant document not found.")
    if document.scan_status != "AVAILABLE":
        raise ApiError(422, "FILE_SCAN_PENDING", "Certificate evidence must pass scanning first.")
    row.certificate_document_id = document.id
    row.certificate_issued = True
    changed(row, actor.user.id)
    audit(
        db,
        "training_attendance.certificate_issued",
        actor.audit_actor,
        "training_attendance",
        row.id,
        request,
    )
    db.commit()
    return row
