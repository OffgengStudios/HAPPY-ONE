from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from app.core.errors import ApiError
from app.integrations.cv_parser import CvParser, get_cv_parser
from app.modules.cv_parser import service
from app.modules.cv_parser.models import ParserJob, ParserResult
from app.modules.cv_parser.schemas import ReviewInput
from app.modules.iam.dependencies import Database, Principal, require
from app.modules.supply.models import Document, Participant

router = APIRouter(tags=["cv-parser"])
Parser = Annotated[CvParser, Depends(get_cv_parser)]
View = Annotated[Principal, Depends(require("participant:view", "cv:view", "cv_parse:view"))]
Run = Annotated[
    Principal, Depends(require("participant:view", "cv:view", "cv_parse:view", "cv_parse:run"))
]
Review = Annotated[
    Principal,
    Depends(
        require(
            "participant:view",
            "participant:edit",
            "cv:view",
            "cv_parse:view",
            "cv_parse:review",
        )
    ),
]


@router.post("/cv/{identifier}/parse", status_code=201)
def parse_cv(
    identifier: UUID, db: Database, actor: Run, request: Request, parser: Parser
) -> dict[str, Any]:
    document = db.get(Document, identifier)
    if not document or document.archived_at:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "CV document not found.")
    participant = db.get(Participant, document.participant_id)
    if not participant or participant.archived_at:
        raise ApiError(404, "PARTICIPANT_NOT_FOUND", "Participant not found.")
    return service.job_view(
        db, service.start_job(db, document, participant, actor, request, parser)
    )


@router.get("/cv/{identifier}/parser-jobs")
def document_jobs(identifier: UUID, db: Database, actor: View) -> dict[str, Any]:
    if not db.get(Document, identifier):
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "CV document not found.")
    rows = db.scalars(
        select(ParserJob)
        .where(ParserJob.document_id == identifier, ParserJob.archived_at.is_(None))
        .order_by(ParserJob.created_at.desc(), ParserJob.id.desc())
        .limit(25)
    )
    return {"items": [service.job_view(db, row) for row in rows]}


@router.get("/cv-parser/jobs/{identifier}")
def job(identifier: UUID, db: Database, actor: View) -> dict[str, Any]:
    row = db.get(ParserJob, identifier)
    if not row or row.archived_at:
        raise ApiError(404, "PARSER_JOB_NOT_FOUND", "Parser job not found.")
    return service.job_view(db, row)


@router.post("/cv-parser/results/{identifier}/review")
def review_result(
    identifier: UUID,
    values: ReviewInput,
    db: Database,
    actor: Review,
    request: Request,
) -> dict[str, Any]:
    row = db.get(ParserResult, identifier)
    if not row:
        raise ApiError(404, "PARSER_RESULT_NOT_FOUND", "Parser result not found.")
    return service.review(db, row, values, actor, request)
