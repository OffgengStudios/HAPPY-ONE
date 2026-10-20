from typing import Any

from email_validator import EmailNotValidError, validate_email
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.integrations.cv_parser.adapter import CvParser, ParserUnavailable
from app.modules.cv_parser.models import ParserJob, ParserResult, ParserReview
from app.modules.cv_parser.schemas import ReviewInput
from app.modules.demand.schemas import normalize_phone
from app.modules.demand.service import changed
from app.modules.iam.actors import AuthorizationContext, staff_user_id
from app.modules.iam.dependencies import Principal
from app.modules.iam.models import now
from app.modules.iam.service import audit
from app.modules.supply.files import verified_bytes
from app.modules.supply.models import Document, Participant, Person, Skill

ALLOWED_FIELDS = {
    "first_name",
    "surname",
    "other_names",
    "phone_raw",
    "email",
    "job_role",
    "sector_code",
    "industry_code",
    "skills",
}
INPUT_CATEGORIES = ["contact", "education", "employment", "identity_name", "skills"]


def _job_view(db: Session, job: ParserJob) -> dict[str, Any]:
    result = db.scalar(select(ParserResult).where(ParserResult.job_id == job.id))
    return {
        "id": job.id,
        "document_id": job.document_id,
        "document_version": job.document_version,
        "status": job.status,
        "provider": job.provider,
        "model": job.model,
        "input_categories": job.input_categories,
        "attempt_count": job.attempt_count,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "version": job.version,
        "result": result_view(db, result) if result else None,
    }


def result_view(db: Session, result: ParserResult) -> dict[str, Any]:
    reviews = list(
        db.scalars(
            select(ParserReview)
            .where(ParserReview.result_id == result.id)
            .order_by(ParserReview.created_at, ParserReview.id)
        )
    )
    return {
        "id": result.id,
        "job_id": result.job_id,
        "schema_version": result.schema_version,
        "provider": result.provider,
        "model": result.model,
        "suggestions": result.suggestions_json,
        "review_status": result.review_status,
        "reviews": [
            {
                "id": item.id,
                "field": item.field,
                "decision": item.decision,
                "original_value": item.original_value_json,
                "approved_value": item.approved_value_json,
                "confidence": item.confidence,
                "reason": item.reason,
                "reviewed_by": item.reviewed_by,
                "created_at": item.created_at,
            }
            for item in reviews
        ],
    }


def start_job(
    db: Session,
    document: Document,
    participant: Participant,
    actor: AuthorizationContext,
    request: Request,
    parser: CvParser,
    *,
    commit: bool = True,
) -> ParserJob:
    if document.document_type != "CV" or document.scan_status != "AVAILABLE":
        raise ApiError(409, "CV_NOT_PARSEABLE", "Only an available, scanned CV can be parsed.")
    active = db.scalar(
        select(ParserJob).where(
            ParserJob.document_id == document.id,
            ParserJob.status.in_(["QUEUED", "RUNNING"]),
            ParserJob.archived_at.is_(None),
        )
    )
    if active:
        raise ApiError(409, "PARSER_JOB_ACTIVE", "This CV already has an active parser job.")
    job = ParserJob(
        document_id=document.id,
        document_version=document.version_number,
        status="QUEUED",
        input_categories=INPUT_CATEGORIES,
        attempt_count=0,
        next_attempt_at=now(),
        created_by=staff_user_id(actor),
        updated_by=staff_user_id(actor),
    )
    db.add(job)
    participant.cv_status = "PARSING"
    changed(participant, staff_user_id(actor))
    db.flush()
    audit(db, "cv_parser.queued", actor.audit_actor, "cv_parser_job", job.id, request)
    if commit:
        db.commit()
        db.refresh(job)
    return job


def process_job(
    db: Session,
    job: ParserJob,
    document: Document,
    participant: Participant,
    parser: CvParser,
) -> ParserJob:
    try:
        output = parser.parse(
            verified_bytes(document), document.mime_type, document.original_filename
        )
        suggestions: list[dict[str, Any]] = []
        seen: set[str] = set()
        for suggestion in output.suggestions:
            if suggestion.field not in ALLOWED_FIELDS or suggestion.field in seen:
                raise ValueError("Parser returned an unsupported or duplicate field.")
            if suggestion.confidence is not None and not 0 <= suggestion.confidence <= 1:
                raise ValueError("Parser returned an invalid confidence value.")
            seen.add(suggestion.field)
            suggestions.append(
                {
                    "field": suggestion.field,
                    "value": suggestion.value,
                    "confidence": suggestion.confidence,
                }
            )
        if not suggestions:
            raise ValueError("Parser returned no reviewable suggestions.")
        job.status = "SUCCEEDED"
        job.provider = output.provider[:100]
        job.model = output.model[:100] if output.model else None
        job.completed_at = now()
        result = ParserResult(
            job_id=job.id,
            provider=job.provider,
            model=job.model,
            suggestions_json=suggestions,
            created_via="INTEGRATION",
        )
        db.add(result)
        participant.cv_status = "REVIEW_REQUIRED"
        audit(
            db,
            "cv_parser.succeeded",
            None,
            "cv_parser_job",
            job.id,
            None,
            changes={"provider": job.provider, "input_categories": INPUT_CATEGORIES},
        )
    except Exception as exc:
        job.status = "FAILED"
        job.completed_at = now()
        if isinstance(exc, ParserUnavailable):
            job.error_code = "PARSER_UNAVAILABLE"
            job.error_message = str(exc)[:500]
        elif isinstance(exc, ValueError):
            job.error_code = "INVALID_OUTPUT"
            job.error_message = str(exc)[:500]
        else:
            job.error_code = "PARSER_FAILED"
            job.error_message = "The CV parser could not process this document."
        participant.cv_status = "READY" if participant.current_cv_id == document.id else "UPLOADED"
        audit(
            db,
            "cv_parser.failed",
            None,
            "cv_parser_job",
            job.id,
            None,
            result="FAILURE",
            changes={"error_code": job.error_code},
        )
    changed(participant, job.created_by)
    changed(job, job.created_by)
    job.lease_expires_at = None
    job.lease_owner = None
    job.next_attempt_at = None
    db.commit()
    db.refresh(job)
    return job


def _clean_value(field: str, value: Any) -> Any:
    if field == "skills":
        if not isinstance(value, list) or not 1 <= len(value) <= 100:
            raise ApiError(422, "INVALID_REVIEW_VALUE", "Skills must be a non-empty list.")
        cleaned = []
        for item in value:
            if not isinstance(item, str) or not 1 <= len(item.strip()) <= 150:
                raise ApiError(422, "INVALID_REVIEW_VALUE", "Check the reviewed skills.")
            cleaned.append(item.strip())
        return list(dict.fromkeys(cleaned))
    if field == "other_names" and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ApiError(422, "INVALID_REVIEW_VALUE", "Check the reviewed parser value.")
    value = value.strip()
    maximum = 254 if field == "email" else 150
    if len(value) > maximum:
        raise ApiError(422, "INVALID_REVIEW_VALUE", "The reviewed parser value is too long.")
    if field == "phone_raw":
        try:
            normalize_phone(value)
        except ValueError:
            raise ApiError(
                422, "INVALID_REVIEW_VALUE", "Check the reviewed phone number."
            ) from None
    if field == "email":
        try:
            value = validate_email(value, check_deliverability=False).normalized
        except EmailNotValidError:
            raise ApiError(
                422, "INVALID_REVIEW_VALUE", "Check the reviewed email address."
            ) from None
    return value


def review(
    db: Session,
    result: ParserResult,
    values: ReviewInput,
    actor: Principal,
    request: Request,
) -> dict[str, Any]:
    job = db.get(ParserJob, result.job_id)
    document = db.get(Document, job.document_id) if job else None
    if not job or not document:
        raise ApiError(404, "PARSER_RESULT_NOT_FOUND", "Parser result not found.")
    participant = db.scalar(
        select(Participant).where(Participant.id == document.participant_id).with_for_update()
    )
    if not participant:
        raise ApiError(404, "PARTICIPANT_NOT_FOUND", "Participant not found.")
    if participant.version != values.participant_version:
        raise ApiError(
            409, "VERSION_CONFLICT", "The participant changed. Refresh and review again."
        )
    suggestions = {item["field"]: item for item in result.suggestions_json}
    reviewed = set(
        db.scalars(select(ParserReview.field).where(ParserReview.result_id == result.id))
    )
    person = db.get(Person, participant.person_id)
    assert person
    for decision in values.decisions:
        suggestion = suggestions.get(decision.field)
        if not suggestion:
            raise ApiError(422, "UNKNOWN_SUGGESTION", "A reviewed field is not in this result.")
        if decision.field in reviewed:
            raise ApiError(
                409, "SUGGESTION_ALREADY_REVIEWED", "This suggestion was already reviewed."
            )
        approved = None
        if decision.decision in {"APPROVE", "EDIT"}:
            approved = _clean_value(
                decision.field,
                suggestion["value"] if decision.decision == "APPROVE" else decision.value,
            )
            if decision.field == "skills":
                existing = {
                    item.casefold()
                    for item in db.scalars(
                        select(Skill.skill_name).where(
                            Skill.participant_id == participant.id, Skill.archived_at.is_(None)
                        )
                    )
                }
                for name in approved:
                    if name.casefold() not in existing:
                        db.add(
                            Skill(
                                participant_id=participant.id,
                                skill_name=name,
                                source="CV_PARSER_REVIEW",
                                verified=False,
                                created_by=actor.user.id,
                            )
                        )
            elif decision.field in {"first_name", "surname", "other_names", "phone_raw", "email"}:
                setattr(person, decision.field, approved)
                if decision.field == "phone_raw":
                    normalized_phone = normalize_phone(approved)
                    assert normalized_phone is not None
                    person.phone_normalized = normalized_phone
                if decision.field in {"first_name", "surname", "other_names"}:
                    person.normalized_name = " ".join(
                        filter(None, [person.first_name, person.other_names, person.surname])
                    ).casefold()
                changed(person, actor.user.id)
            else:
                setattr(participant, decision.field, approved)
        db.add(
            ParserReview(
                result_id=result.id,
                field=decision.field,
                decision=decision.decision,
                original_value_json=suggestion["value"],
                approved_value_json=approved,
                confidence=suggestion.get("confidence"),
                reviewed_by=actor.user.id,
                reason=decision.reason,
            )
        )
        reviewed.add(decision.field)
    decisions = list(
        db.scalars(select(ParserReview.decision).where(ParserReview.result_id == result.id))
    ) + [item.decision for item in values.decisions]
    if len(reviewed) == len(suggestions):
        result.review_status = (
            "APPROVED" if any(item != "REJECT" for item in decisions) else "REJECTED"
        )
        participant.current_cv_id = document.id
        participant.cv_status = "READY"
    else:
        result.review_status = "PARTIALLY_REVIEWED"
    changed(participant, actor.user.id)
    audit(
        db,
        "cv_parser.reviewed",
        actor.audit_actor,
        "cv_parser_result",
        result.id,
        request,
        changes={
            "fields": [item.field for item in values.decisions],
            "status": result.review_status,
        },
    )
    db.commit()
    return result_view(db, result)


job_view = _job_view
