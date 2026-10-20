from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select

from app.core.errors import ApiError
from app.integrations.employer_portal import service
from app.integrations.employer_portal.auth import EmployerPortalActor
from app.integrations.employer_portal.models import EmployerSubmission
from app.integrations.employer_portal.schemas import (
    ConvertSubmission,
    PortalSubmission,
    ReviewSubmission,
)
from app.modules.iam.dependencies import Database, Principal, require
from app.modules.iam.service import audit, page_query

router = APIRouter(tags=["employer-portal-integration"])
Read = Annotated[Principal, Depends(require("employer_submission:view"))]
Manage = Annotated[
    Principal, Depends(require("employer_submission:view", "employer_submission:manage"))
]
Convert = Annotated[
    Principal,
    Depends(
        require(
            "employer_submission:view",
            "employer_submission:manage",
            "organization:create",
            "organization_contact:edit",
            "partnership:edit",
            "vacancy:create",
        )
    ),
]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.post("/integrations/employer-portal/submissions", status_code=202)
def receive_submission(
    data: PortalSubmission, db: Database, actor: EmployerPortalActor, request: Request
) -> dict[str, Any]:
    row, replayed = service.receive(db, data, actor, request)
    return {**service.view(row), "replayed": replayed}


@router.get("/integrations/employer-portal/submissions")
def submissions(
    db: Database,
    actor: Read,
    status: str | None = None,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    query = select(EmployerSubmission)
    if status:
        query = query.where(EmployerSubmission.status == status)
    page = page_query(query, EmployerSubmission, db, limit, cursor)
    return {
        "items": [service.view(row) for row in page["rows"]],
        "next_cursor": page["next_cursor"],
    }


@router.get("/integrations/employer-portal/submissions/{identifier}")
def submission(identifier: UUID, db: Database, actor: Read) -> dict[str, Any]:
    row = db.get(EmployerSubmission, identifier)
    if not row:
        raise ApiError(404, "EMPLOYER_SUBMISSION_NOT_FOUND", "Submission not found.")
    from app.integrations.intake.models import IntakeDocument, PublicIntake

    documents = db.scalars(
        select(IntakeDocument)
        .join(PublicIntake)
        .where(PublicIntake.employer_submission_id == row.id)
    )
    return {
        **service.view(row, include_payload=True),
        "possible_duplicates": service.duplicate_candidates(db, service.decrypt(row))
        if "organization:view" in actor.permissions
        else [],
        "documents": [
            {"id": str(doc.id), "kind": doc.kind, "scan_status": doc.scan_status}
            for doc in documents
        ],
    }


@router.get(
    "/integrations/employer-portal/submissions/{identifier}/documents/{document_id}/download"
)
def download_document(
    identifier: UUID, document_id: UUID, db: Database, actor: Read, request: Request
) -> Response:
    from urllib.parse import quote

    from app.integrations.intake.models import IntakeDocument, PublicIntake
    from app.modules.supply.files import verified_bytes

    document = db.scalar(
        select(IntakeDocument)
        .join(PublicIntake)
        .where(
            PublicIntake.employer_submission_id == identifier,
            IntakeDocument.id == document_id,
        )
    )
    if document is None:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "Document not found.")
    resource = "job_description" if document.kind == "JD" else "partnership_document"
    if not {resource + ":view", resource + ":download"} <= actor.permissions:
        raise ApiError(
            403, "PERMISSION_DENIED", "You do not have permission to download this document."
        )
    if document.scan_status != "AVAILABLE":
        raise ApiError(409, "FILE_SCAN_PENDING", "This document is not available for download.")
    content = verified_bytes(document)
    audit(
        db,
        "employer_intake.document_downloaded",
        actor.audit_actor,
        "intake_document",
        document.id,
        request,
    )
    db.commit()
    return Response(
        content,
        media_type=document.mime_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": "attachment; filename*=UTF-8''"
            + quote(document.original_filename),
        },
    )


@router.post("/integrations/employer-portal/submissions/{identifier}/convert")
def convert(
    identifier: UUID, values: ConvertSubmission, db: Database, actor: Convert, request: Request
) -> dict[str, Any]:
    row = db.get(EmployerSubmission, identifier)
    if not row:
        raise ApiError(404, "EMPLOYER_SUBMISSION_NOT_FOUND", "Submission not found.")
    return service.view(service.convert(db, row, values, actor, request))


@router.post("/integrations/employer-portal/submissions/{identifier}/review")
def review(
    identifier: UUID, values: ReviewSubmission, db: Database, actor: Manage, request: Request
) -> dict[str, Any]:
    row = db.get(EmployerSubmission, identifier)
    if not row:
        raise ApiError(404, "EMPLOYER_SUBMISSION_NOT_FOUND", "Submission not found.")
    if row.version != values.version:
        raise ApiError(
            409, "RECORD_VERSION_CONFLICT", "This submission changed. Refresh before saving."
        )
    if row.status not in {"NEW", "NEEDS_REVIEW"}:
        raise ApiError(
            409, "SUBMISSION_NOT_REVIEWABLE", "Only pending submissions can be reviewed."
        )
    row.status = "REJECTED" if values.decision == "REJECT" else "ARCHIVED"
    row.review_notes = values.reason
    row.version += 1
    audit(
        db,
        "employer_portal.submission_reviewed",
        actor.audit_actor,
        "employer_submission",
        row.id,
        request,
        changes={"decision": values.decision, "reason": values.reason},
    )
    db.commit()
    return service.view(row)
