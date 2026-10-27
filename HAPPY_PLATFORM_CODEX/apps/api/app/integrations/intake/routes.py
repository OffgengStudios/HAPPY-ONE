from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import settings
from app.core.errors import ApiError
from app.integrations.employer_portal.service import cipher
from app.integrations.intake import metrics, service
from app.integrations.intake.models import IntakeDocument, PublicIntake
from app.integrations.intake.schemas import (
    DuplicateResolution,
    EmployerSubmission,
    IntakeReview,
    ParticipantSubmission,
)
from app.integrations.intake.sources import PARTICIPANT_SOURCE, PARTICIPANT_SOURCES
from app.modules.iam.dependencies import Database, Principal, require
from app.modules.iam.service import audit

router = APIRouter(tags=["public-intake"])
employer_router = APIRouter(tags=["legacy-employer-intake"])
Read = Annotated[Principal, Depends(require("integration_event:view"))]
Manage = Annotated[Principal, Depends(require("integration_event:manage"))]


def protected(request: Request, db: Database) -> None:
    service.protect(db, request)


@router.get("/participant-intake/config")
def configuration() -> dict[str, Any]:
    from app.modules.supply.schemas import TRAINING_INTEREST_LABELS

    return {
        "source_system": PARTICIPANT_SOURCE,
        "training_interests": TRAINING_INTEREST_LABELS,
        "privacy_notice_version": settings.supply_privacy_notice_version,
        "privacy_notice": settings.supply_privacy_notice_text,
        "accepting_submissions": bool(
            settings.supply_privacy_notice_version and settings.supply_privacy_notice_text
        ),
        "required_sections": settings.supply_required_sections,
        "required_fields": settings.supply_required_fields,
        "file_max_bytes": settings.file_max_bytes,
    }


@router.post("/participant-intake", status_code=202, dependencies=[Depends(protected)])
def submit_participant(
    request: Request,
    db: Database,
    payload: Annotated[str, Form(max_length=262144)],
    cv: Annotated[UploadFile | None, File()] = None,
) -> dict[str, Any]:
    try:
        data = ParticipantSubmission.model_validate_json(payload)
    except ValidationError:
        raise ApiError(422, "VALIDATION_ERROR", "Check the submitted participant fields.") from None
    if (
        not settings.supply_privacy_notice_text
        or data.consent.notice_version != settings.supply_privacy_notice_version
    ):
        raise ApiError(
            422,
            "PRIVACY_NOTICE_REQUIRED",
            "Review the current programme privacy notice before submitting.",
        )
    uploads = []
    if cv:
        uploads.append(
            (cv.filename or "", cv.content_type or "", cv.file.read(settings.file_max_bytes + 1))
        )
    keys: list[str] = []
    try:
        row, replay = service.receipt(
            db, PARTICIPANT_SOURCE, data.submission_id, service.submitted_payload(data), uploads
        )
        if replay:
            return service.public_receipt(row)
        staged = service.upload_stage(db, row, "CV", uploads[0], keys) if uploads else None
        service.apply_participant(db, row, data, request, staged)
        db.commit()
        metrics.participant_received.add(1)
        return service.public_receipt(row)
    except Exception:
        service.compensate(db, keys)
        raise


@employer_router.get("/employer-intake/config")
def employer_configuration() -> dict[str, Any]:
    return {
        "notice": settings.employer_intake_notice_text,
        "accepting_submissions": bool(settings.employer_intake_notice_text),
        "file_max_bytes": settings.file_max_bytes,
    }


@employer_router.post("/employer-intake", status_code=202, dependencies=[Depends(protected)])
def submit_employer(
    request: Request,
    db: Database,
    payload: Annotated[str, Form(max_length=262144)],
    files: Annotated[list[UploadFile] | None, File()] = None,
) -> dict[str, Any]:
    from app.integrations.employer_portal import service as portal
    from app.integrations.employer_portal.schemas import PortalSubmission
    from app.modules.iam.actors import AuditActor

    try:
        data = EmployerSubmission.model_validate_json(payload)
    except ValidationError:
        raise ApiError(422, "VALIDATION_ERROR", "Check the employer submission fields.") from None
    if not settings.employer_intake_notice_text:
        raise ApiError(
            503, "INTAKE_NOTICE_REQUIRED", "The employer intake notice is not configured."
        )
    files = files or []
    if len(files) != len(data.documents) or len(files) > 5:
        raise ApiError(
            422, "DOCUMENT_METADATA_REQUIRED", "Check the submitted document descriptions."
        )
    uploads = [
        (file.filename or "", file.content_type or "", file.file.read(settings.file_max_bytes + 1))
        for file in files
    ]
    keys: list[str] = []
    try:
        row, replay = service.receipt(
            db, "EMPLOYER_INTAKE", data.submission_id, data.model_dump(mode="json"), uploads
        )
        if replay:
            return service.public_receipt(row)
        staged = [
            service.upload_stage(db, row, descriptor.kind, upload, keys, descriptor.vacancy_index)
            for descriptor, upload in zip(data.documents, uploads, strict=True)
        ]
        values = data.model_dump(mode="json", exclude={"documents", "company_fax"})
        values["submission_id"] = str(data.submission_id)
        # This marker is not signature evidence or MOU approval. Only stored,
        # scanned files are linked by the authenticated staff conversion.
        values["signature_file_id"] = "PUBLIC_INTAKE_NO_EXTERNAL_SIGNATURE"
        values["document_ids"] = [str(doc.id) for doc in staged]
        actor = service.PublicActor()
        actor.audit_actor = AuditActor("INTEGRATION", "EMPLOYER_INTAKE_PUBLIC")
        submission, _ = portal.receive(
            db, PortalSubmission.model_validate(values), actor, request, commit=False
        )
        row.employer_submission_id = submission.id
        row.status = "NEEDS_REVIEW"
        audit(
            db,
            "employer_intake.submitted",
            actor.audit_actor,
            "employer_submission",
            submission.id,
            request,
        )
        db.commit()
        metrics.employer_received.add(1)
        return service.public_receipt(row)
    except Exception:
        service.compensate(db, keys)
        raise


@router.get("/intake-operations")
def operations(db: Database, actor: Read) -> dict[str, Any]:
    from app.modules.cv_parser.models import ParserJob

    rows = db.scalars(select(PublicIntake).order_by(PublicIntake.received_at.desc()).limit(100))
    items: list[dict[str, Any]] = [
        {
            "id": str(row.id),
            "source": row.source,
            "status": row.status,
            "received_at": row.received_at,
            "participant_id": row.participant_id,
            "employer_submission_id": row.employer_submission_id,
        }
        for row in rows
    ]
    jobs = db.scalars(select(ParserJob).order_by(ParserJob.created_at.desc()).limit(100))
    items.extend(
        {
            "id": str(job.id),
            "source": "CV_PARSER",
            "status": "RETRYING" if job.status == "QUEUED" and job.attempt_count else job.status,
            "received_at": job.created_at,
            "document_id": job.document_id,
            "error_code": job.error_code,
            "attempt_count": job.attempt_count,
        }
        for job in jobs
    )
    return {"items": items}


@router.get("/intake-operations/{identifier}")
def intake_detail(identifier: UUID, db: Database, actor: Read, request: Request) -> dict[str, Any]:
    row = db.get(PublicIntake, identifier)
    if row is None:
        raise ApiError(404, "INTAKE_NOT_FOUND", "Submission not found.")
    import json

    if (
        row.source in PARTICIPANT_SOURCES
        and not {"participant:view", "participant_sensitive:view"} <= actor.permissions
    ):
        raise ApiError(
            403, "PERMISSION_DENIED", "You do not have permission to view participant evidence."
        )
    if row.source == "EMPLOYER_INTAKE" and "employer_submission:view" not in actor.permissions:
        raise ApiError(
            403, "PERMISSION_DENIED", "You do not have permission to view employer evidence."
        )
    audit(db, "intake.evidence_viewed", actor.audit_actor, "public_intake", row.id, request)
    db.commit()
    try:
        payload = json.loads(cipher().decrypt(row.payload_ciphertext.encode()))
    except Exception:
        raise ApiError(
            503, "INTAKE_EVIDENCE_UNAVAILABLE", "Protected submission evidence is unavailable."
        ) from None
    if isinstance(payload.get("identity"), dict):
        # Identity values stay non-readable just as in the protected domain API.
        identity = payload["identity"]
        payload["identity"] = {
            "government_id_type": identity.get("government_id_type"),
            "has_government_id": bool(identity.get("government_id")),
        }
    return {
        "id": str(row.id),
        "source": row.source,
        "status": row.status,
        "payload": payload,
        "documents": [
            {"id": str(doc.id), "kind": doc.kind, "scan_status": doc.scan_status}
            for doc in db.scalars(select(IntakeDocument).where(IntakeDocument.intake_id == row.id))
        ],
    }


@router.post("/intake-operations/{identifier}/review")
def review(
    identifier: UUID, data: IntakeReview, db: Database, actor: Manage, request: Request
) -> dict[str, Any]:
    row = db.scalar(select(PublicIntake).where(PublicIntake.id == identifier).with_for_update())
    if row is None or row.status != "NEEDS_REVIEW":
        raise ApiError(409, "INTAKE_NOT_REVIEWABLE", "This submission is not awaiting review.")
    row.status = "REJECTED"
    audit(
        db,
        "intake.reviewed",
        actor.audit_actor,
        "public_intake",
        row.id,
        request,
        changes={"decision": data.decision, "reason": data.reason},
    )
    db.commit()
    return {"id": str(row.id), "status": row.status}


@router.post("/intake-operations/{identifier}/resolve")
def resolve_duplicate(
    identifier: UUID, data: DuplicateResolution, db: Database, actor: Manage, request: Request
) -> dict[str, Any]:
    from app.modules.external_references.models import ExternalReference
    from app.modules.supply.models import Participant

    if not {"participant:view", "participant:edit"} <= actor.permissions:
        raise ApiError(403, "PERMISSION_DENIED", "You do not have permission for this action.")
    row = db.scalar(select(PublicIntake).where(PublicIntake.id == identifier).with_for_update())
    if row is None or row.source not in PARTICIPANT_SOURCES or row.status != "NEEDS_REVIEW":
        raise ApiError(
            409, "INTAKE_NOT_REVIEWABLE", "This participant submission is not awaiting review."
        )
    participant = db.get(Participant, data.existing_participant_id)
    if participant is None or participant.archived_at:
        raise ApiError(404, "PARTICIPANT_NOT_FOUND", "Participant not found.")
    row.participant_id = participant.id
    row.status = "APPLIED"
    db.add(
        ExternalReference(
            entity_type="PARTICIPANT",
            entity_id=participant.id,
            external_system=row.source,
            external_id=str(row.submission_id),
        )
    )
    audit(
        db,
        "participant_intake.duplicate_resolved",
        actor.audit_actor,
        "public_intake",
        row.id,
        request,
        changes={"participant_id": str(participant.id), "reason": data.reason},
    )
    # Resolution links provenance only. It does not overwrite the staff record,
    # revive consent, approve intake documents or merge people automatically.
    db.commit()
    return {"id": str(row.id), "status": row.status}


@router.post("/intake-operations/{identifier}/documents/{document_id}/rescan")
def rescan_document(
    identifier: UUID, document_id: UUID, db: Database, actor: Manage, request: Request
) -> dict[str, Any]:
    import hashlib

    from app.modules.supply import files
    from app.storage.s3 import get_storage_client

    staged = db.scalar(
        select(IntakeDocument)
        .where(IntakeDocument.id == document_id, IntakeDocument.intake_id == identifier)
        .with_for_update()
    )
    if staged is None or staged.scan_status != "SCANNING":
        raise ApiError(
            409, "DOCUMENT_NOT_SCAN_PENDING", "This intake document is not awaiting a scan."
        )
    try:
        stream = get_storage_client().get_object(Bucket=settings.s3_bucket, Key=staged.storage_key)[
            "Body"
        ]
        try:
            content = stream.read(settings.file_max_bytes + 1)
        finally:
            stream.close()
        if (
            len(content) != staged.size_bytes
            or hashlib.sha256(content).hexdigest() != staged.sha256
        ):
            raise ValueError("integrity")
    except Exception:
        raise ApiError(
            503, "STORAGE_UNAVAILABLE", "The private document could not be verified."
        ) from None
    staged.scan_status = files.scan(content)
    if staged.kind == "CV" and staged.linked_document_id:
        from app.integrations.cv_parser import get_cv_parser
        from app.modules.cv_parser import service as parsing
        from app.modules.supply.models import Document, Participant

        if not {"cv:edit", "cv_parse:run"} <= actor.permissions:
            raise ApiError(403, "PERMISSION_DENIED", "You do not have permission to process CVs.")

        document = db.get(Document, staged.linked_document_id)
        if document:
            document.scan_status = staged.scan_status
            if document.scan_status == "AVAILABLE":
                participant = db.get(Participant, document.participant_id)
                if participant:
                    parsing.start_job(
                        db, document, participant, actor, request, get_cv_parser(), commit=False
                    )
    audit(
        db,
        "intake.document_scanned",
        actor.audit_actor,
        "intake_document",
        staged.id,
        request,
        changes={"scan_status": staged.scan_status},
    )
    db.commit()
    return {"id": str(staged.id), "scan_status": staged.scan_status}
