from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
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
    return service.view(row, include_payload=True)


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
