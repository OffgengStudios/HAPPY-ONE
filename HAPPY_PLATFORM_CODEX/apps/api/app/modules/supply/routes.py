from datetime import timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.errors import ApiError
from app.modules.demand.schemas import Archive, Version
from app.modules.demand.service import assignable, changed, get_record
from app.modules.iam.dependencies import Database, Principal, require
from app.modules.iam.models import AuditEvent, User, now
from app.modules.iam.service import audit, page_query, permissions_for
from app.modules.supply import files
from app.modules.supply import schemas as data
from app.modules.supply import service as s
from app.modules.supply.models import (
    Consent,
    Document,
    Education,
    Experience,
    Participant,
    Person,
    Skill,
)

router = APIRouter(tags=["supply"])
Read = Annotated[Principal, Depends(require("participant:view"))]
Create = Annotated[Principal, Depends(require("participant:view", "participant:create"))]
Edit = Annotated[Principal, Depends(require("participant:view", "participant:edit"))]
SensitiveRead = Annotated[
    Principal, Depends(require("participant:view", "participant_sensitive:view"))
]
SensitiveEdit = Annotated[
    Principal,
    Depends(
        require(
            "participant:view",
            "participant:edit",
            "participant_sensitive:view",
            "participant_sensitive:edit",
        )
    ),
]
CVRead = Annotated[Principal, Depends(require("participant:view", "cv:view"))]
CVEdit = Annotated[Principal, Depends(require("participant:view", "cv:view", "cv:edit"))]
CVDownload = Annotated[Principal, Depends(require("participant:view", "cv:view", "cv:download"))]
Workspace = Annotated[Principal, Depends(require("participant:view", "workspace_supply:view"))]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.get("/participants")
def participants(
    db: Database,
    actor: Read,
    q: Annotated[str, Query(max_length=200)] = "",
    onboarding_status: data.OnboardingStatus | None = None,
    readiness_status: data.ReadinessStatus | None = None,
    availability_status: data.AvailabilityStatus | None = None,
    owner_id: UUID | None = None,
    archived: bool = False,
    pending_only: bool = False,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    query = (
        select(Participant)
        .join(Person, Participant.person_id == Person.id)
        .where(
            Participant.archived_at.is_not(None) if archived else Participant.archived_at.is_(None)
        )
    )
    if q:
        search = "%" + q.replace("%", "\\%").replace("_", "\\_").lower() + "%"
        query = query.where(
            (Person.normalized_name.ilike(search))
            | Participant.participant_code.ilike(search)
            | Person.phone_normalized.ilike(search)
        )
    if pending_only:
        query = query.where(
            Participant.onboarding_status.in_(["NOT_STARTED", "IN_PROGRESS", "BLOCKED"])
        )
    for column, value in (
        (Participant.onboarding_status, onboarding_status),
        (Participant.readiness_status, readiness_status),
        (Participant.availability_status, availability_status),
        (Participant.assigned_user_id, owner_id),
    ):
        if value is not None:
            query = query.where(column == value)
    page = page_query(query, Participant, db, limit, cursor)
    return {
        "items": s.participant_views(db, page["rows"]),
        "next_cursor": page["next_cursor"],
    }


@router.post("/participants/duplicate-check")
def duplicate_check(values: data.Intake, db: Database, actor: Create) -> dict[str, Any]:
    return {"matches": s.duplicates(db, values.model_dump())}


@router.post("/participants", status_code=201)
def create(values: data.Intake, db: Database, actor: Create, request: Request) -> dict[str, Any]:
    return s.participant_view(db, s.create(db, values, actor, request))


@router.get("/participants/{identifier}")
def detail(identifier: UUID, db: Database, actor: Read) -> dict[str, Any]:
    return s.participant_view(db, get_record(db, Participant, identifier))


@router.patch("/participants/{identifier}")
def assignment(
    identifier: UUID, values: data.Assignment, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    row = s.lock(db, identifier, values.version)
    assignable(db, values.assigned_user_id, "participant:edit")
    if row.assigned_user_id != values.assigned_user_id:
        row.owner_assigned_at = now() if values.assigned_user_id else None
    for key, value in values.model_dump(exclude={"version", "reason"}).items():
        setattr(row, key, value)
    changed(row, actor.user.id)
    s.save(
        db,
        row,
        actor,
        request,
        "participant.updated",
        {
            "fields": ["assigned_user_id", "priority", "next_action", "next_action_due_at"],
            "reason": values.reason,
        },
    )
    return s.participant_view(db, row)


@router.post("/participants/{identifier}/archive")
def archive(
    identifier: UUID, values: Archive, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    row = s.lock(db, identifier, values.version)
    row.archived_at = now()
    changed(row, actor.user.id)
    s.save(db, row, actor, request, "participant.archived", {"reason": values.reason})
    return s.participant_view(db, row)


@router.get("/participants/{identifier}/onboarding")
def onboarding(identifier: UUID, db: Database, actor: Read) -> dict[str, Any]:
    row = get_record(db, Participant, identifier)
    result = s.participant_view(db, row)
    for name, model in (("education", Education), ("experience", Experience), ("skills", Skill)):
        result[name] = [
            s.child_view(child)
            for child in db.scalars(
                select(model)
                .where(model.participant_id == row.id, model.archived_at.is_(None))
                .order_by(model.created_at, model.id)
            )
        ]
    return result


@router.patch("/participants/{identifier}/onboarding/{section}")
def section(
    identifier: UUID,
    section: str,
    values: dict[str, Any],
    db: Database,
    actor: Edit,
    request: Request,
) -> dict[str, Any]:
    schema = s.SECTION_SCHEMAS.get(section)
    if not schema:
        raise ApiError(404, "SECTION_NOT_FOUND", "This onboarding section is not supported.")
    if (
        section == "demographics"
        and not {"participant_sensitive:view", "participant_sensitive:edit"} <= actor.permissions
    ):
        raise ApiError(403, "PERMISSION_DENIED", "You do not have permission to edit demographics.")
    try:
        parsed = schema.model_validate(values)
    except ValidationError:
        raise ApiError(422, "VALIDATION_ERROR", "Check the submitted section fields.") from None
    row = s.lock(db, identifier, parsed.version)
    s.section_write(db, row, section, parsed, actor, request)
    return s.participant_view(db, row)


@router.post("/participants/{identifier}/onboarding/complete")
def complete(
    identifier: UUID, values: data.Complete, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    row = s.lock(db, identifier, values.version)
    s.complete(db, row, values, actor, request)
    return s.participant_view(db, row)


@router.post("/participants/{identifier}/onboarding/transition")
def state(
    identifier: UUID, values: data.OnboardingState, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    row = s.lock(db, identifier, values.version)
    if row.onboarding_status == values.to_status:
        raise ApiError(422, "INVALID_STATUS_TRANSITION", "Choose a different onboarding status.")
    before = row.onboarding_status
    row.onboarding_status = values.to_status
    changed(row, actor.user.id)
    s.save(
        db,
        row,
        actor,
        request,
        "participant.onboarding_status_changed",
        {"from": before, "to": row.onboarding_status, "reason": values.reason},
    )
    return s.participant_view(db, row)


@router.get("/participants/{identifier}/readiness")
def readiness(identifier: UUID, db: Database, actor: Read) -> dict[str, Any]:
    return s.participant_view(db, get_record(db, Participant, identifier))


@router.get("/participants/{identifier}/lifecycle-summary")
def lifecycle_summary(identifier: UUID, db: Database, actor: Read) -> dict[str, Any]:
    from app.modules.placement.models import Placement
    from app.modules.training.models import TrainingAttendance

    row = get_record(db, Participant, identifier)
    result: dict[str, Any] = {"onboarding": row.onboarding_status}
    if "outcome:view" in actor.permissions:
        from app.modules.merl.models import Outcome

        latest = db.scalar(
            select(Outcome)
            .where(Outcome.participant_id == identifier, Outcome.archived_at.is_(None))
            .order_by(Outcome.as_of_date.desc(), Outcome.created_at.desc(), Outcome.id.desc())
            .limit(1)
        )
        result["employment_outcome"] = (
            "WORKING"
            if latest and latest.currently_working
            else "NOT_WORKING"
            if latest
            else "NOT_RECORDED"
        )
    for key, model, column, permission in (
        ("training", TrainingAttendance, TrainingAttendance.completion_status, "training:view"),
        ("placement", Placement, Placement.status, "placement:view"),
    ):
        result[key] = (
            dict(
                db.execute(
                    select(column, func.count())
                    .where(model.participant_id == identifier, model.archived_at.is_(None))
                    .group_by(column)
                ).all()
            )
            if permission in actor.permissions
            else None
        )
    return result


@router.post("/participants/{identifier}/readiness")
def readiness_write(
    identifier: UUID, values: data.StatusWrite, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    row = s.lock(db, identifier, values.version)
    if row.onboarding_status == "WITHDRAWN":
        raise ApiError(409, "PARTICIPANT_WITHDRAWN", "Reopen onboarding before changing readiness.")
    before = {"readiness": row.readiness_status, "availability": row.availability_status}
    row.readiness_status = values.readiness_status
    row.availability_status = values.availability_status
    changed(row, actor.user.id)
    s.save(
        db,
        row,
        actor,
        request,
        "participant.readiness_changed",
        {
            "from": before,
            "to": {"readiness": row.readiness_status, "availability": row.availability_status},
            "reason": values.reason,
        },
    )
    return s.participant_view(db, row)


@router.get("/participants/{identifier}/consents")
def consents(
    identifier: UUID, db: Database, actor: Read, limit: Limit = 25, cursor: str | None = None
) -> dict[str, Any]:
    get_record(db, Participant, identifier)
    page = page_query(
        select(Consent).where(Consent.participant_id == identifier), Consent, db, limit, cursor
    )
    return {
        "items": [s.child_view(row) for row in page["rows"]],
        "next_cursor": page["next_cursor"],
    }


@router.post("/participants/{identifier}/consents", status_code=201)
def consent_create(
    identifier: UUID, values: data.ConsentWrite, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    row = s.lock(db, identifier, values.version)
    return s.child_view(s.record_consent(db, row, values, actor, request))


@router.post("/consents/{identifier}/withdraw")
def consent_withdraw(
    identifier: UUID, values: Archive, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    consent = get_record(db, Consent, identifier)
    row = s.lock(db, consent.participant_id, values.version)
    db.refresh(consent)
    s.withdraw_consent(db, row, consent, values.reason, actor, request)
    return s.participant_view(db, row)


@router.get("/participants/{identifier}/sensitive")
def sensitive(
    identifier: UUID, db: Database, actor: SensitiveRead, request: Request
) -> dict[str, Any]:
    row = get_record(db, Participant, identifier)
    audit(db, "participant.sensitive_field_viewed", actor.user.id, "participants", row.id, request)
    db.commit()
    return s.sensitive_view(db, row)


@router.patch("/participants/{identifier}/sensitive")
def sensitive_write(
    identifier: UUID,
    values: data.SensitiveWrite,
    db: Database,
    actor: SensitiveEdit,
    request: Request,
) -> dict[str, Any]:
    row = s.lock(db, identifier, values.version)
    s.save_sensitive(db, row, values, actor, request)
    return s.sensitive_view(db, row)


@router.patch("/participants/{identifier}/identity")
def identity(
    identifier: UUID,
    values: data.IdentityWrite,
    db: Database,
    actor: SensitiveEdit,
    request: Request,
) -> dict[str, Any]:
    row = s.lock(db, identifier, values.version)
    s.save_identity(db, row, values, actor, request)
    return s.sensitive_view(db, row)


@router.get("/participants/{identifier}/activity")
def activity(
    identifier: UUID, db: Database, actor: Read, limit: Limit = 25, cursor: str | None = None
) -> dict[str, Any]:
    get_record(db, Participant, identifier)
    page = page_query(
        select(AuditEvent).where(
            AuditEvent.entity_type == "participants", AuditEvent.entity_id == identifier
        ),
        AuditEvent,
        db,
        limit,
        cursor,
    )
    return {
        "items": [
            {
                "id": row.id,
                "event_code": row.event_code,
                "occurred_at": row.occurred_at,
                "actor_id": row.actor_id,
                "actor_type": row.actor_type,
            }
            for row in page["rows"]
        ],
        "next_cursor": page["next_cursor"],
    }


@router.get("/participants/{identifier}/cv/versions")
@router.get("/participants/{identifier}/cv")
def cvs(
    identifier: UUID, db: Database, actor: CVRead, limit: Limit = 25, cursor: str | None = None
) -> dict[str, Any]:
    row = get_record(db, Participant, identifier)
    page = page_query(
        select(Document).where(Document.participant_id == identifier), Document, db, limit, cursor
    )
    return {
        "items": [s.child_view(doc) for doc in page["rows"]],
        "next_cursor": page["next_cursor"],
        "current_cv_id": row.current_cv_id,
    }


@router.post("/participants/{identifier}/cv", status_code=201)
def cv_upload(
    identifier: UUID,
    db: Database,
    actor: CVEdit,
    request: Request,
    file: Annotated[UploadFile, File()],
    version: Annotated[int, Form(ge=1)],
) -> dict[str, Any]:
    row = s.lock(db, identifier, version)
    from app.core.config import settings

    content = file.file.read(settings.file_max_bytes + 1)
    document = files.upload(
        db, row, content, file.filename or "", file.content_type or "", actor.user.id
    )
    changed(row, actor.user.id)
    s.save(
        db,
        row,
        actor,
        request,
        "document.uploaded",
        {"scan_status": document.scan_status, "document_id": str(document.id)},
    )
    return s.child_view(document)


@router.post("/files/{identifier}/rescan")
def rescan(
    identifier: UUID, values: Version, db: Database, actor: CVEdit, request: Request
) -> dict[str, Any]:
    document = get_record(db, Document, identifier)
    row = s.lock(db, document.participant_id, values.version)
    db.refresh(document)
    if document.scan_status != "SCANNING":
        raise ApiError(
            409, "INVALID_STATUS_TRANSITION", "Only scan-pending files can be rescanned."
        )
    document.scan_status = files.scan(files.verified_bytes(document))
    changed(document, actor.user.id)
    changed(row, actor.user.id)
    s.save(
        db,
        row,
        actor,
        request,
        "document.scan_completed",
        {"document_id": str(document.id), "scan_status": document.scan_status},
    )
    return s.child_view(document)


@router.post("/cv/{identifier}/approve")
def approve(
    identifier: UUID, values: Version, db: Database, actor: CVEdit, request: Request
) -> dict[str, Any]:
    document = get_record(db, Document, identifier)
    row = s.lock(db, document.participant_id, values.version)
    db.refresh(document)
    if document.scan_status != "AVAILABLE" or document.archived_at:
        raise ApiError(409, "FILE_SCAN_PENDING", "Only an available scanned CV can be approved.")
    row.current_cv_id = document.id
    row.cv_status = "READY"
    changed(row, actor.user.id)
    s.save(db, row, actor, request, "cv.approved", {"document_id": str(document.id)})
    return s.participant_view(db, row)


@router.post("/participants/{identifier}/cv/not-required")
def cv_waive(
    identifier: UUID, values: data.CVWaiver, db: Database, actor: CVEdit, request: Request
) -> dict[str, Any]:
    row = s.lock(db, identifier, values.version)
    row.current_cv_id = None
    row.cv_status = "NOT_REQUIRED"
    changed(row, actor.user.id)
    s.save(db, row, actor, request, "cv.not_required", {"reason": values.reason})
    return s.participant_view(db, row)


@router.get("/files/{identifier}/download")
def download(identifier: UUID, db: Database, actor: CVDownload, request: Request) -> Response:
    doc = get_record(db, Document, identifier)
    row = get_record(db, Participant, doc.participant_id)
    if row.archived_at or doc.archived_at or doc.scan_status != "AVAILABLE":
        raise ApiError(409, "FILE_SCAN_PENDING", "This file is not available for download.")
    content = files.verified_bytes(doc)
    audit(
        db,
        "document.downloaded_sensitive",
        actor.user.id,
        "participants",
        row.id,
        request,
        changes={"document_id": str(doc.id)},
    )
    db.commit()
    return Response(
        content,
        media_type=doc.mime_type,
        headers={
            "Content-Disposition": 'attachment; filename="cv-'
            + str(doc.version_number)
            + (".pdf" if doc.mime_type == files.PDF else ".docx")
            + '"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/files/{identifier}/archive")
def archive_file(
    identifier: UUID, values: Archive, db: Database, actor: CVEdit, request: Request
) -> dict[str, Any]:
    doc = get_record(db, Document, identifier)
    row = s.lock(db, doc.participant_id, values.version)
    db.refresh(doc)
    if doc.archived_at:
        raise ApiError(409, "RECORD_ARCHIVED", "This document is already archived.")
    files.archive(doc, row)
    changed(doc, actor.user.id)
    changed(row, actor.user.id)
    s.save(
        db,
        row,
        actor,
        request,
        "document.archived",
        {"document_id": str(doc.id), "reason": values.reason},
    )
    return s.participant_view(db, row)


@router.get("/supply/owners")
def owners(db: Database, actor: Workspace) -> list[dict[str, Any]]:
    return [
        {"id": u.id, "full_name": u.full_name}
        for u in db.scalars(
            select(User).where(User.is_active.is_(True)).order_by(User.full_name, User.id)
        )
        if {"participant:edit", "participant:view"} <= permissions_for(u)
    ]


@router.get("/supply/dashboard")
def dashboard(db: Database, actor: Workspace) -> dict[str, Any]:
    base = select(func.count()).select_from(Participant).where(Participant.archived_at.is_(None))
    registered = db.scalar(base) or 0
    complete_count = db.scalar(base.where(Participant.onboarding_status == "COMPLETE")) or 0
    job_ready = (
        db.scalar(
            base.where(
                Participant.onboarding_status == "COMPLETE",
                Participant.readiness_status == "JOB_READY",
                Participant.availability_status == "AVAILABLE",
            )
        )
        or 0
    )
    pending = (
        db.scalar(
            base.where(Participant.onboarding_status.in_(["NOT_STARTED", "IN_PROGRESS", "BLOCKED"]))
        )
        or 0
    )
    return {
        "metrics": [
            {
                "code": "SUPPLY-REGISTERED",
                "label": "Registered participants",
                "value": registered,
                "filters": {},
            },
            {
                "code": "KPI-SUP-001",
                "label": "Onboarding complete",
                "value": complete_count,
                "denominator": registered,
                "percentage": round(complete_count / registered * 100, 2) if registered else 0,
                "filters": {"onboarding_status": "COMPLETE"},
            },
            {
                "code": "KPI-SUP-002",
                "label": "Job ready",
                "value": job_ready,
                "filters": {
                    "onboarding_status": "COMPLETE",
                    "readiness_status": "JOB_READY",
                    "availability_status": "AVAILABLE",
                },
            },
            {
                "code": "SUPPLY-ONBOARDING-PENDING",
                "label": "Onboarding pending",
                "value": pending,
                "filters": {"pending_only": "true"},
            },
        ]
    }


@router.get("/supply/my-work")
def work(
    db: Database, actor: Workspace, limit: Limit = 25, cursor: str | None = None
) -> dict[str, Any]:
    page = page_query(
        select(Participant).where(
            Participant.assigned_user_id == actor.user.id,
            Participant.archived_at.is_(None),
            Participant.onboarding_status != "WITHDRAWN",
        ),
        Participant,
        db,
        limit,
        cursor,
    )
    items = []
    for row in page["rows"]:
        item = s.participant_view(db, row)
        due = row.next_action_due_at
        item["due_state"] = (
            "UNSCHEDULED"
            if not due
            else "OVERDUE"
            if due.date() < now().date()
            else "TODAY"
            if due.date() == now().date()
            else "UPCOMING"
        )
        item["recently_assigned"] = bool(
            row.owner_assigned_at and row.owner_assigned_at >= now() - timedelta(days=7)
        )
        item["owner_name"] = actor.user.full_name
        items.append(item)
    return {"items": items, "next_cursor": page["next_cursor"]}
