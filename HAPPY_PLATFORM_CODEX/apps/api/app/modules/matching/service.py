import base64
import binascii
import json
from datetime import timedelta
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session

from app.modules.demand.models import Organization, Vacancy
from app.modules.demand.schemas import json_value
from app.modules.demand.service import assignable, changed, fail, get_record, writable
from app.modules.iam.dependencies import Principal
from app.modules.iam.models import User, now
from app.modules.iam.service import audit, permissions_for
from app.modules.matching import schemas as s
from app.modules.matching.models import (
    TERMINAL,
    CandidateHistory,
    CandidateVacancy,
    EmployerDecision,
    Interview,
    InterviewHistory,
    Screening,
)
from app.modules.supply.models import Participant, Person
from app.modules.supply.service import assert_submission_eligible, full_name, participant_view

PHASE_6 = {"STARTED", "AWAITING_FIRST_INCOME", "CONFIRMED_PLACEMENT"}
EDGES: dict[str, set[str]] = {
    "POTENTIAL_MATCH": {"RECRUITER_REVIEW", "NOT_INTERESTED", "WITHDRAWN", "EMPLOYER_CANCELLED"},
    "RECRUITER_REVIEW": {
        "PRE_SCREEN",
        "NOT_INTERESTED",
        "UNREACHABLE",
        "WITHDRAWN",
        "EMPLOYER_CANCELLED",
    },
    "PRE_SCREEN": {
        "QUALIFIED",
        "REJECTED",
        "NOT_INTERESTED",
        "UNREACHABLE",
        "SALARY_DECLINED",
        "LOCATION_DECLINED",
        "WITHDRAWN",
        "EMPLOYER_CANCELLED",
    },
    "QUALIFIED": {
        "SUBMITTED",
        "NOT_INTERESTED",
        "SALARY_DECLINED",
        "LOCATION_DECLINED",
        "WITHDRAWN",
        "EMPLOYER_CANCELLED",
    },
    "SUBMITTED": {"INTERVIEW", "EMPLOYER_DECISION", "REJECTED", "WITHDRAWN", "EMPLOYER_CANCELLED"},
    "INTERVIEW": {"EMPLOYER_DECISION", "NO_SHOW", "REJECTED", "WITHDRAWN", "EMPLOYER_CANCELLED"},
    "EMPLOYER_DECISION": {"INTERVIEW", "SELECTED", "REJECTED", "WITHDRAWN", "EMPLOYER_CANCELLED"},
    "SELECTED": {"FAILED_TO_START", "WITHDRAWN", "EMPLOYER_CANCELLED"},
}
CANDIDATE_FIELDS = (
    "id",
    "version",
    "participant_id",
    "vacancy_id",
    "status",
    "owner_id",
    "source",
    "priority",
    "next_action",
    "next_action_due_at",
    "pre_screen_result",
    "submitted_at",
    "selected_at",
    "closed_reason",
    "closed_note",
    "created_at",
    "updated_at",
    "archived_at",
    "source_system",
    "created_via",
    "match_strength",
    "match_explanation_json",
)
INTERVIEW_FIELDS = (
    "id",
    "version",
    "candidate_vacancy_id",
    "scheduled_at",
    "timezone",
    "format",
    "location_or_link",
    "status",
    "outcome",
    "notes",
    "created_at",
    "updated_at",
    "source_system",
    "created_via",
)


def chronological_page(
    query: Any, model: Any, column: Any, db: Session, limit: int, cursor: str | None
) -> dict[str, Any]:
    if cursor:
        try:
            position = s.TimeCursor.model_validate(
                json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
            )
        except (ValueError, binascii.Error):
            fail("INVALID_CURSOR", "The pagination cursor is invalid.", 422)
        query = query.where(
            or_(column > position.at, and_(column == position.at, model.id > position.id))
        )
    rows = list(db.scalars(query.order_by(column, model.id).limit(limit + 1)))
    more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if more:
        last = rows[-1]
        position = s.TimeCursor(id=last.id, at=getattr(last, column.key))
        next_cursor = base64.urlsafe_b64encode(position.model_dump_json().encode()).decode()
    return {"rows": rows, "next_cursor": next_cursor}


def validate_owner(db: Session, identifier: UUID | None) -> None:
    assignable(db, identifier, "candidate_pipeline:edit")
    if identifier is not None:
        user = db.get(User, identifier)
        if user is None or not {
            "candidate_pipeline:view",
            "participant:view",
            "vacancy:view",
        } <= permissions_for(user):
            fail("INVALID_OWNER", "Choose staff with candidate and parent-record access.", 422)


def candidate_views(db: Session, rows: list[CandidateVacancy]) -> list[dict[str, Any]]:
    if not rows:
        return []
    people = {
        participant.id: (participant, person)
        for participant, person in db.execute(
            select(Participant, Person)
            .join(Person, Person.id == Participant.person_id)
            .where(Participant.id.in_({row.participant_id for row in rows}))
        )
    }
    vacancies = {
        vacancy.id: (vacancy, organization)
        for vacancy, organization in db.execute(
            select(Vacancy, Organization)
            .join(Organization, Organization.id == Vacancy.organization_id)
            .where(Vacancy.id.in_({row.vacancy_id for row in rows}))
        )
    }
    owners = {
        user.id: user.full_name
        for user in db.scalars(
            select(User).where(User.id.in_({row.owner_id for row in rows if row.owner_id}))
        )
    }
    return [
        {
            **{key: json_value(getattr(row, key)) for key in CANDIDATE_FIELDS},
            "participant_name": full_name(people[row.participant_id][1]),
            "participant_code": people[row.participant_id][0].participant_code,
            "onboarding_status": people[row.participant_id][0].onboarding_status,
            "participant_archived": bool(people[row.participant_id][0].archived_at),
            "vacancy_title": vacancies[row.vacancy_id][0].title,
            "vacancy_status": vacancies[row.vacancy_id][0].status,
            "organization_name": vacancies[row.vacancy_id][1].name,
            "owner_name": owners.get(row.owner_id) if row.owner_id else None,
            "allowed_transitions": sorted(
                EDGES.get(row.status, set()) - {"QUALIFIED", "INTERVIEW", "SELECTED"}
            ),
        }
        for row in rows
    ]


def candidate_view(db: Session, row: CandidateVacancy, detail: bool = False) -> dict[str, Any]:
    result = candidate_views(db, [row])[0]
    if detail:
        result["participant"] = participant_view(
            db, get_record(db, Participant, row.participant_id)
        )
    return result


def lock_candidates(db: Session, identifiers: list[UUID]) -> dict[UUID, CandidateVacancy]:
    records = list(db.scalars(select(CandidateVacancy).where(CandidateVacancy.id.in_(identifiers))))
    if len(records) != len(identifiers):
        fail("RECORD_NOT_FOUND", "A candidate relationship does not exist.", 404)
    # Lock all parents before children in the same order for single and bulk writes.
    list(
        db.scalars(
            select(Participant)
            .where(Participant.id.in_({row.participant_id for row in records}))
            .order_by(Participant.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    vacancy_ids = {row.vacancy_id for row in records}
    organization_ids = set(
        db.scalars(select(Vacancy.organization_id).where(Vacancy.id.in_(vacancy_ids)))
    )
    list(
        db.scalars(
            select(Organization)
            .where(Organization.id.in_(organization_ids))
            .order_by(Organization.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    list(
        db.scalars(
            select(Vacancy)
            .where(Vacancy.id.in_(vacancy_ids))
            .order_by(Vacancy.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    return {
        row.id: row
        for row in db.scalars(
            select(CandidateVacancy)
            .where(CandidateVacancy.id.in_(identifiers))
            .order_by(CandidateVacancy.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }


def locked(db: Session, identifier: UUID, version: int) -> CandidateVacancy:
    row = lock_candidates(db, [identifier])[identifier]
    writable(row, version)
    return row


def live_parents(db: Session, row: CandidateVacancy, submission: bool = False) -> Participant:
    participant = get_record(db, Participant, row.participant_id)
    vacancy = get_record(db, Vacancy, row.vacancy_id)
    organization = get_record(db, Organization, vacancy.organization_id)
    if participant.archived_at or participant.onboarding_status == "WITHDRAWN":
        fail("PARTICIPANT_INACTIVE", "This participant is archived or withdrawn.", 422)
    if (
        vacancy.archived_at
        or organization.archived_at
        or vacancy.status in {"CLOSED", "CANCELLED", "FULLY_FILLED"}
    ):
        fail("VACANCY_INACTIVE", "This vacancy or employer is no longer available.", 422)
    if submission:
        if vacancy.status not in {"ACTIVE", "PARTIALLY_FILLED"}:
            fail("VACANCY_NOT_ACTIVE", "Employer submission requires an active vacancy.", 422)
        assert_submission_eligible(db, participant)
    return participant


def history(
    db: Session, row: CandidateVacancy, previous: str | None, actor: Principal, reason: str | None
) -> None:
    identity = actor.audit_actor
    db.add(
        CandidateHistory(
            candidate_vacancy_id=row.id,
            from_status=previous,
            to_status=row.status,
            reason=reason,
            actor_type=identity.actor_type,
            actor_id=identity.actor_id,
        )
    )


def save(
    db: Session,
    row: CandidateVacancy | Interview,
    actor: Principal,
    request: Request,
    event: str,
    fields: list[str],
) -> None:
    db.flush()
    audit(
        db, event, actor.audit_actor, row.__tablename__, row.id, request, changes={"fields": fields}
    )
    db.commit()


def create(
    db: Session, values: s.CandidateCreate, actor: Principal, request: Request
) -> CandidateVacancy:
    get_record(db, Participant, values.participant_id, True)
    get_record(db, Vacancy, values.vacancy_id, True)
    row = CandidateVacancy(**values.model_dump(), created_by=actor.user.id)
    live_parents(db, row)
    validate_owner(db, values.owner_id)
    duplicate = db.scalar(
        select(CandidateVacancy.id).where(
            CandidateVacancy.participant_id == values.participant_id,
            CandidateVacancy.vacancy_id == values.vacancy_id,
            CandidateVacancy.archived_at.is_(None),
            CandidateVacancy.status.not_in(TERMINAL),
        )
    )
    if duplicate:
        fail(
            "CANDIDATE_ALREADY_LINKED",
            "An active relationship already links this participant and vacancy.",
        )
    row.owner_assigned_at = now() if values.owner_id else None
    db.add(row)
    db.flush()
    history(db, row, None, actor, None)
    save(
        db,
        row,
        actor,
        request,
        "candidate_vacancy.created",
        ["participant_id", "vacancy_id", "owner_id"],
    )
    return row


def validate_transition(
    db: Session, row: CandidateVacancy, target: str, reason: str | None, evidence: bool = False
) -> None:
    if target in PHASE_6:
        fail(
            "PLACEMENT_WORKFLOW_REQUIRED",
            "Actual start and first-income confirmation use the placement workflow.",
            422,
        )
    if target not in EDGES.get(row.status, set()):
        fail("INVALID_TRANSITION", "This candidate transition is not allowed.", 422)
    if target in TERMINAL and not reason:
        fail("REASON_REQUIRED", "Record a reason for closing this candidate relationship.", 422)
    if not evidence and target in {"QUALIFIED", "INTERVIEW", "SELECTED"}:
        fail(
            "WORKFLOW_EVIDENCE_REQUIRED",
            "Use screening, interview scheduling or employer decision to record this action.",
            422,
        )
    if target == "SUBMITTED" or target == "SELECTED":
        live_parents(db, row, submission=True)
    if target == "EMPLOYER_DECISION" and row.status == "SUBMITTED" and not reason:
        fail("REASON_REQUIRED", "Explain the employer decision without an interview.", 422)


def apply_transition(
    db: Session,
    row: CandidateVacancy,
    target: str,
    reason: str | None,
    actor: Principal,
    request: Request,
) -> None:
    previous = row.status
    row.status = target
    if target == "SUBMITTED":
        row.submitted_at = now()
    if target == "SELECTED":
        row.selected_at = now()
    if target in TERMINAL:
        row.closed_reason, row.closed_note = target, reason
    changed(row, actor.user.id)
    history(db, row, previous, actor, reason)
    audit(
        db,
        "candidate_vacancy.status_changed",
        actor.audit_actor,
        "candidate_vacancies",
        row.id,
        request,
        changes={"from_status": previous, "to_status": target},
    )
    if target == "SUBMITTED":
        audit(
            db,
            "candidate_vacancy.submitted",
            actor.audit_actor,
            "candidate_vacancies",
            row.id,
            request,
            changes={"fields": ["status", "submitted_at"]},
        )


def transition(
    db: Session, identifier: UUID, values: s.Transition, actor: Principal, request: Request
) -> CandidateVacancy:
    row = locked(db, identifier, values.version)
    validate_transition(db, row, values.to_status, values.reason)
    apply_transition(db, row, values.to_status, values.reason, actor, request)
    db.commit()
    return row


def screen(
    db: Session, identifier: UUID, values: s.ScreeningInput, actor: Principal, request: Request
) -> CandidateVacancy:
    row = locked(db, identifier, values.version)
    if row.status != "PRE_SCREEN":
        fail("SCREENING_STAGE_REQUIRED", "Open pre-screen before recording screening.", 422)
    target = (
        "QUALIFIED"
        if values.result == "QUALIFIED"
        else "REJECTED"
        if values.result == "NOT_QUALIFIED"
        else None
    )
    if target:
        validate_transition(db, row, target, values.notes, evidence=True)
    db.add(
        Screening(
            candidate_vacancy_id=row.id,
            **values.model_dump(exclude={"version"}),
            created_by=actor.user.id,
        )
    )
    row.pre_screen_result = values.result
    if target:
        apply_transition(db, row, target, values.notes, actor, request)
    else:
        changed(row, actor.user.id)
    save(db, row, actor, request, "candidate_vacancy.pre_screen_recorded", ["pre_screen_result"])
    return row


def decide(
    db: Session, identifier: UUID, values: s.Decision, actor: Principal, request: Request
) -> CandidateVacancy:
    row = locked(db, identifier, values.version)
    if row.status != "EMPLOYER_DECISION":
        fail(
            "EMPLOYER_DECISION_STAGE_REQUIRED",
            "Move to employer decision before recording the decision.",
            422,
        )
    if values.decision != "PENDING":
        validate_transition(db, row, values.decision, values.reason, evidence=True)
    db.add(
        EmployerDecision(
            candidate_vacancy_id=row.id,
            decision=values.decision,
            reason=values.reason,
            created_by=actor.user.id,
        )
    )
    if values.decision == "PENDING":
        changed(row, actor.user.id)
    else:
        apply_transition(db, row, values.decision, values.reason, actor, request)
    save(db, row, actor, request, "candidate_vacancy.employer_decision_recorded", ["decision"])
    return row


def interview_views(db: Session, rows: list[Interview]) -> list[dict[str, Any]]:
    candidates = (
        list(
            db.scalars(
                select(CandidateVacancy).where(
                    CandidateVacancy.id.in_({row.candidate_vacancy_id for row in rows})
                )
            )
        )
        if rows
        else []
    )
    descriptions = {row["id"]: row for row in candidate_views(db, candidates)}
    return [
        {
            **{key: json_value(getattr(row, key)) for key in INTERVIEW_FIELDS},
            "participant_name": descriptions[str(row.candidate_vacancy_id)]["participant_name"],
            "vacancy_title": descriptions[str(row.candidate_vacancy_id)]["vacancy_title"],
            "candidate_status": descriptions[str(row.candidate_vacancy_id)]["status"],
        }
        for row in rows
    ]


def interview_history(
    db: Session, row: Interview, previous: str | None, actor: Principal, reason: str | None
) -> None:
    identity = actor.audit_actor
    db.add(
        InterviewHistory(
            interview_id=row.id,
            from_status=previous,
            to_status=row.status,
            scheduled_at=row.scheduled_at,
            reason=reason,
            actor_type=identity.actor_type,
            actor_id=identity.actor_id,
        )
    )


def interview_create(
    db: Session, values: s.InterviewCreate, actor: Principal, request: Request
) -> Interview:
    candidate = locked(db, values.candidate_vacancy_id, values.candidate_version)
    if candidate.status not in {"SUBMITTED", "INTERVIEW", "EMPLOYER_DECISION"}:
        fail("SUBMISSION_REQUIRED", "Submit the candidate before scheduling an interview.", 422)
    live_parents(db, candidate, submission=True)
    row = Interview(**values.model_dump(exclude={"candidate_version"}), created_by=actor.user.id)
    db.add(row)
    db.flush()
    interview_history(db, row, None, actor, None)
    if candidate.status in {"SUBMITTED", "EMPLOYER_DECISION"}:
        apply_transition(db, candidate, "INTERVIEW", None, actor, request)
    else:
        changed(candidate, actor.user.id)
    save(
        db,
        row,
        actor,
        request,
        "interview.created",
        ["scheduled_at", "format", "candidate_vacancy_id"],
    )
    return row


def interview_locked(
    db: Session, identifier: UUID, version: int
) -> tuple[Interview, CandidateVacancy]:
    preliminary = get_record(db, Interview, identifier)
    candidate = lock_candidates(db, [preliminary.candidate_vacancy_id])[
        preliminary.candidate_vacancy_id
    ]
    row = get_record(db, Interview, identifier, True)
    writable(row, version)
    if candidate.archived_at or candidate.status in TERMINAL | PHASE_6 | {"SELECTED"}:
        fail(
            "CANDIDATE_CLOSED",
            "This candidate relationship no longer accepts interview changes.",
            422,
        )
    return row, candidate


def interview_action(
    db: Session,
    identifier: UUID,
    version: int,
    target: str,
    actor: Principal,
    request: Request,
    reason: str,
    scheduled_at: Any = None,
    outcome: str | None = None,
) -> Interview:
    row, candidate = interview_locked(db, identifier, version)
    allowed = {
        "SCHEDULED": {"ATTENDED", "NO_SHOW", "RESCHEDULED", "CANCELLED"},
        "RESCHEDULED": {"ATTENDED", "NO_SHOW", "RESCHEDULED", "CANCELLED"},
        "NO_SHOW": {"RESCHEDULED", "CANCELLED"},
        "ATTENDED": {"COMPLETED"},
    }
    if target not in allowed.get(row.status, set()):
        fail("INVALID_INTERVIEW_TRANSITION", "This interview action is not allowed.", 422)
    previous = row.status
    row.status = target
    if scheduled_at is not None:
        row.scheduled_at = scheduled_at
    if outcome:
        row.outcome = outcome
        if candidate.status == "INTERVIEW":
            apply_transition(db, candidate, "EMPLOYER_DECISION", reason, actor, request)
    changed(row, actor.user.id)
    interview_history(db, row, previous, actor, reason)
    save(
        db,
        row,
        actor,
        request,
        "interview.outcome_recorded" if outcome else "interview.status_changed",
        ["status", "scheduled_at", "outcome"],
    )
    return row


def work_bucket(row: CandidateVacancy) -> dict[str, Any]:
    due = row.next_action_due_at
    today = now().date()
    return {
        "due_state": "OVERDUE"
        if due and due.date() < today
        else "DUE_TODAY"
        if due and due.date() == today
        else "UPCOMING",
        "recently_assigned": bool(
            row.owner_assigned_at and row.owner_assigned_at >= now() - timedelta(days=7)
        ),
    }


def active_relationship(participant_id: Any, vacancy_id: UUID) -> Any:
    return exists(
        select(CandidateVacancy.id).where(
            CandidateVacancy.participant_id == participant_id,
            CandidateVacancy.vacancy_id == vacancy_id,
            CandidateVacancy.archived_at.is_(None),
            CandidateVacancy.status.not_in(TERMINAL),
        )
    )
