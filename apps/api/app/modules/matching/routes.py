from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select

from app.modules.demand.models import Requirement, Vacancy
from app.modules.demand.schemas import Version
from app.modules.demand.service import changed, fail, get_record, writable
from app.modules.iam.dependencies import Database, Principal, require
from app.modules.iam.models import User, now
from app.modules.iam.service import page_query, permissions_for
from app.modules.matching import schemas as data
from app.modules.matching import service as s
from app.modules.matching.models import (
    TERMINAL,
    CandidateHistory,
    CandidateVacancy,
    EmployerDecision,
    Interview,
    InterviewHistory,
    Screening,
)
from app.modules.supply.models import Participant, Person, Skill
from app.modules.supply.service import full_name

router = APIRouter(tags=["matching"])
Read = Annotated[
    Principal, Depends(require("candidate_pipeline:view", "participant:view", "vacancy:view"))
]
Edit = Annotated[
    Principal,
    Depends(
        require(
            "candidate_pipeline:view", "candidate_pipeline:edit", "participant:view", "vacancy:view"
        )
    ),
]
InterviewRead = Annotated[
    Principal,
    Depends(
        require("interview:view", "candidate_pipeline:view", "participant:view", "vacancy:view")
    ),
]
InterviewEdit = Annotated[
    Principal,
    Depends(
        require(
            "interview:view",
            "interview:edit",
            "candidate_pipeline:view",
            "candidate_pipeline:edit",
            "participant:view",
            "vacancy:view",
        )
    ),
]
Limit = Annotated[int, Query(ge=1, le=100)]


def _matches(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "IN":
        return bool(actual in expected)
    if operator == "EQ":
        return bool(actual == expected)
    if actual is None:
        return False
    return bool(actual >= expected if operator == "GTE" else actual <= expected)


def _match_explanation(
    participant: Participant,
    person: Person,
    requirements: list[Requirement],
    skills: set[str],
) -> dict[str, Any]:
    if not requirements:
        return {
            "match_strength": None,
            "positive_reasons": [],
            "potential_gaps": ["Vacancy criteria have not been configured."],
            "confidence": "LOW",
        }
    participant_fields = {
        key: getattr(participant, key)
        for key in (
            "readiness_status",
            "availability_status",
            "education_status",
            "employment_status",
            "sector_code",
            "industry_code",
            "job_type",
            "job_role",
            "work_region_code",
            "work_district_code",
            "work_community",
        )
        if hasattr(participant, key)
    }
    location_fields = {
        "region_code": person.region_code,
        "district_code": person.district_code,
        "community": person.community,
    }
    positive: list[str] = []
    gaps: list[str] = []
    earned = total = known = 0.0
    for criterion in requirements:
        weight = float(criterion.weight)
        total += weight
        name = criterion.criterion_key.replace("_", " ")
        if criterion.criterion_type.upper() == "SKILL":
            matched = criterion.criterion_key.casefold() in skills
            known += weight
        else:
            fields = (
                location_fields
                if criterion.criterion_type.upper() == "LOCATION"
                else participant_fields
            )
            actual = fields.get(criterion.criterion_key)
            matched = _matches(actual, criterion.operator, criterion.value_json)
            if actual is not None:
                known += weight
        if matched:
            earned += weight
            positive.append(f"Matches {name}.")
        elif criterion.is_required:
            gaps.append(f"Required {name} is missing or does not match.")
        else:
            gaps.append(f"Preferred {name} is not confirmed.")
    confidence_ratio = known / total if total else 0
    return {
        "match_strength": round(earned / total * 100) if total else None,
        "positive_reasons": positive,
        "potential_gaps": gaps,
        "confidence": "HIGH"
        if confidence_ratio >= 0.8
        else "MEDIUM"
        if confidence_ratio >= 0.5
        else "LOW",
    }


@router.get("/candidate-vacancies")
def candidates(
    db: Database,
    actor: Read,
    status: data.Stage | None = None,
    participant_id: UUID | None = None,
    vacancy_id: UUID | None = None,
    owner_id: UUID | None = None,
    q: Annotated[str, Query(max_length=200)] = "",
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    query = (
        select(CandidateVacancy)
        .join(Participant, Participant.id == CandidateVacancy.participant_id)
        .join(Person, Person.id == Participant.person_id)
        .join(Vacancy, Vacancy.id == CandidateVacancy.vacancy_id)
        .where(CandidateVacancy.archived_at.is_(None))
    )
    for column, value in (
        (CandidateVacancy.status, status),
        (CandidateVacancy.participant_id, participant_id),
        (CandidateVacancy.vacancy_id, vacancy_id),
        (CandidateVacancy.owner_id, owner_id),
    ):
        if value is not None:
            query = query.where(column == value)
    if q:
        text = "%" + q.replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(
            or_(
                Person.normalized_name.ilike(text),
                Participant.participant_code.ilike(text),
                Vacancy.title.ilike(text),
            )
        )
    result = page_query(query, CandidateVacancy, db, limit, cursor)
    return {"items": s.candidate_views(db, result["rows"]), "next_cursor": result["next_cursor"]}


@router.post("/candidate-vacancies", status_code=201)
def create(
    values: data.CandidateCreate, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    return s.candidate_view(db, s.create(db, values, actor, request), detail=True)


@router.post("/candidate-vacancies/bulk-transition")
def bulk(
    values: data.BulkTransition, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    rows = s.lock_candidates(db, [row.id for row in values.candidates])
    for value in values.candidates:
        row = rows[value.id]
        writable(row, value.version)
        s.validate_transition(db, row, values.to_status, values.reason)
    for value in values.candidates:
        s.apply_transition(db, rows[value.id], values.to_status, values.reason, actor, request)
    db.commit()
    return {"items": s.candidate_views(db, list(rows.values()))}


@router.get("/candidate-vacancies/{identifier}")
def detail(identifier: UUID, db: Database, actor: Read) -> dict[str, Any]:
    return s.candidate_view(db, get_record(db, CandidateVacancy, identifier), detail=True)


@router.patch("/candidate-vacancies/{identifier}")
def patch(
    identifier: UUID, values: data.CandidatePatch, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    row = s.locked(db, identifier, values.version)
    if row.status in TERMINAL | s.PHASE_6:
        fail("CANDIDATE_CLOSED", "Closed relationships cannot be reassigned.", 422)
    s.validate_owner(db, values.owner_id)
    if row.owner_id != values.owner_id:
        row.owner_assigned_at = now() if values.owner_id else None
    for key, value in values.model_dump(exclude={"version", "reason"}).items():
        setattr(row, key, value)
    changed(row, actor.user.id)
    s.save(
        db,
        row,
        actor,
        request,
        "candidate_vacancy.updated",
        list(data.CandidateFields.model_fields),
    )
    return s.candidate_view(db, row, detail=True)


@router.post("/candidate-vacancies/{identifier}/transition")
def transition(
    identifier: UUID, values: data.Transition, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    return s.candidate_view(db, s.transition(db, identifier, values, actor, request), detail=True)


@router.post("/candidate-vacancies/{identifier}/submit")
def submit(
    identifier: UUID, values: Version, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    return s.candidate_view(
        db,
        s.transition(
            db,
            identifier,
            data.Transition(version=values.version, to_status="SUBMITTED"),
            actor,
            request,
        ),
        detail=True,
    )


@router.post("/candidate-vacancies/{identifier}/pre-screen")
def screen(
    identifier: UUID, values: data.ScreeningInput, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    return s.candidate_view(db, s.screen(db, identifier, values, actor, request), detail=True)


@router.post("/candidate-vacancies/{identifier}/employer-decision")
def decide(
    identifier: UUID, values: data.Decision, db: Database, actor: Edit, request: Request
) -> dict[str, Any]:
    return s.candidate_view(db, s.decide(db, identifier, values, actor, request), detail=True)


@router.get("/candidate-vacancies/{identifier}/history")
def history(
    identifier: UUID, db: Database, actor: Read, limit: Limit = 25, cursor: str | None = None
) -> dict[str, Any]:
    get_record(db, CandidateVacancy, identifier)
    result = s.chronological_page(
        select(CandidateHistory).where(CandidateHistory.candidate_vacancy_id == identifier),
        CandidateHistory,
        CandidateHistory.occurred_at,
        db,
        limit,
        cursor,
    )
    return {
        "items": [
            {
                key: getattr(row, key)
                for key in (
                    "id",
                    "from_status",
                    "to_status",
                    "reason",
                    "actor_type",
                    "actor_id",
                    "occurred_at",
                )
            }
            for row in result["rows"]
        ],
        "next_cursor": result["next_cursor"],
    }


@router.get("/candidate-vacancies/{identifier}/screenings")
def screenings(
    identifier: UUID, db: Database, actor: Read, limit: Limit = 25, cursor: str | None = None
) -> dict[str, Any]:
    get_record(db, CandidateVacancy, identifier)
    result = s.chronological_page(
        select(Screening).where(Screening.candidate_vacancy_id == identifier),
        Screening,
        Screening.created_at,
        db,
        limit,
        cursor,
    )
    return {
        "items": [
            {
                key: getattr(row, key)
                for key in (
                    "id",
                    "result",
                    "participant_interested",
                    "availability_confirmed",
                    "salary_accepted",
                    "location_accepted",
                    "notes",
                    "created_at",
                )
            }
            for row in result["rows"]
        ],
        "next_cursor": result["next_cursor"],
    }


@router.get("/candidate-vacancies/{identifier}/employer-decisions")
def decisions(
    identifier: UUID, db: Database, actor: Read, limit: Limit = 25, cursor: str | None = None
) -> dict[str, Any]:
    get_record(db, CandidateVacancy, identifier)
    result = s.chronological_page(
        select(EmployerDecision).where(EmployerDecision.candidate_vacancy_id == identifier),
        EmployerDecision,
        EmployerDecision.created_at,
        db,
        limit,
        cursor,
    )
    return {
        "items": [
            {key: getattr(row, key) for key in ("id", "decision", "reason", "created_at")}
            for row in result["rows"]
        ],
        "next_cursor": result["next_cursor"],
    }


@router.get("/matching/owners")
def owners(db: Database, actor: Read) -> list[dict[str, Any]]:
    required = {
        "candidate_pipeline:view",
        "candidate_pipeline:edit",
        "participant:view",
        "vacancy:view",
    }
    return [
        {"id": user.id, "full_name": user.full_name}
        for user in db.scalars(
            select(User).where(User.is_active.is_(True)).order_by(User.full_name, User.id)
        )
        if required <= permissions_for(user)
    ]


@router.get("/matching/dashboard")
def dashboard(db: Database, actor: Read) -> dict[str, Any]:
    counts = dict(
        db.execute(
            select(CandidateVacancy.status, func.count())
            .where(CandidateVacancy.archived_at.is_(None))
            .group_by(CandidateVacancy.status)
        ).all()
    )
    qualified = (
        db.scalar(
            select(func.count())
            .select_from(CandidateVacancy)
            .where(
                CandidateVacancy.pre_screen_result == "QUALIFIED",
                CandidateVacancy.archived_at.is_(None),
            )
        )
        or 0
    )
    submitted = (
        db.scalar(
            select(func.count())
            .select_from(CandidateVacancy)
            .where(
                CandidateVacancy.submitted_at.is_not(None), CandidateVacancy.archived_at.is_(None)
            )
        )
        or 0
    )
    interviewed = (
        db.scalar(
            select(func.count(func.distinct(Interview.candidate_vacancy_id))).where(
                Interview.status.in_({"ATTENDED", "COMPLETED"}), Interview.archived_at.is_(None)
            )
        )
        if "interview:view" in actor.permissions
        else None
    )
    return {
        "stage_counts": counts,
        "metrics": [
            {"label": label, "value": counts.get(stage, 0), "status": stage}
            for label, stage in (
                ("Pre-screen", "PRE_SCREEN"),
                ("Qualified", "QUALIFIED"),
                ("Submitted", "SUBMITTED"),
                ("Selected", "SELECTED"),
            )
        ],
        "submission_conversion": {
            "numerator": submitted,
            "denominator": qualified,
            "rate": round(submitted / qualified * 100, 2) if qualified else None,
        },
        "interview_conversion": {
            "numerator": interviewed,
            "denominator": submitted,
            "rate": round(interviewed / submitted * 100, 2)
            if submitted and interviewed is not None
            else None,
        },
    }


@router.get("/matching/my-work")
def work(db: Database, actor: Read, limit: Limit = 25, cursor: str | None = None) -> dict[str, Any]:
    result = page_query(
        select(CandidateVacancy).where(
            CandidateVacancy.owner_id == actor.user.id,
            CandidateVacancy.status.not_in(TERMINAL | s.PHASE_6),
            CandidateVacancy.archived_at.is_(None),
        ),
        CandidateVacancy,
        db,
        limit,
        cursor,
    )
    return {
        "items": [
            {**item, **s.work_bucket(row)}
            for item, row in zip(s.candidate_views(db, result["rows"]), result["rows"], strict=True)
        ],
        "next_cursor": result["next_cursor"],
    }


@router.post("/vacancies/{identifier}/match-suggestions")
def suggestions(
    identifier: UUID, db: Database, actor: Read, limit: Limit = 25, cursor: str | None = None
) -> dict[str, Any]:
    get_record(db, Vacancy, identifier)
    requirements = list(
        db.scalars(
            select(Requirement)
            .where(Requirement.vacancy_id == identifier, Requirement.archived_at.is_(None))
            .order_by(Requirement.display_order, Requirement.id)
        )
    )
    result = page_query(
        select(Participant).where(
            Participant.archived_at.is_(None),
            Participant.onboarding_status != "WITHDRAWN",
            ~s.active_relationship(Participant.id, identifier),
        ),
        Participant,
        db,
        limit,
        cursor,
    )
    people = {
        person.id: person
        for person in db.scalars(
            select(Person).where(Person.id.in_({row.person_id for row in result["rows"]}))
        )
    }
    participant_ids = {row.id for row in result["rows"]}
    skills_by_participant: dict[UUID, set[str]] = {row.id: set() for row in result["rows"]}
    if participant_ids:
        for skill in db.scalars(
            select(Skill).where(
                Skill.participant_id.in_(participant_ids), Skill.archived_at.is_(None)
            )
        ):
            values = skills_by_participant[skill.participant_id]
            values.add(skill.skill_name.casefold())
            if skill.skill_code:
                values.add(skill.skill_code.casefold())
    return {
        "advisory_only": True,
        "items": [
            {
                "participant_id": row.id,
                "participant_name": full_name(people[row.person_id]),
                "participant_code": row.participant_code,
                "readiness_status": row.readiness_status,
                "availability_status": row.availability_status,
                "onboarding_status": row.onboarding_status,
                **_match_explanation(
                    row,
                    people[row.person_id],
                    requirements,
                    skills_by_participant[row.id],
                ),
                "human_review_required": True,
            }
            for row in result["rows"]
        ],
        "next_cursor": result["next_cursor"],
    }


@router.get("/interviews")
def interviews(
    db: Database,
    actor: InterviewRead,
    candidate_vacancy_id: UUID | None = None,
    status: data.InterviewState | None = None,
    day: date | None = None,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    query = select(Interview).where(Interview.archived_at.is_(None))
    if candidate_vacancy_id:
        query = query.where(Interview.candidate_vacancy_id == candidate_vacancy_id)
    if status:
        query = query.where(Interview.status == status)
    if day:
        start = datetime.combine(day, time.min, tzinfo=UTC)
        query = query.where(
            Interview.scheduled_at >= start, Interview.scheduled_at < start + timedelta(days=1)
        )
    result = s.chronological_page(query, Interview, Interview.scheduled_at, db, limit, cursor)
    items = s.interview_views(db, result["rows"])
    items.sort(key=lambda row: (row["scheduled_at"], row["id"]))
    return {"items": items, "next_cursor": result["next_cursor"]}


@router.post("/interviews", status_code=201)
def interview_create(
    values: data.InterviewCreate, db: Database, actor: InterviewEdit, request: Request
) -> dict[str, Any]:
    return s.interview_views(db, [s.interview_create(db, values, actor, request)])[0]


@router.get("/interviews/{identifier}")
def interview_detail(identifier: UUID, db: Database, actor: InterviewRead) -> dict[str, Any]:
    return s.interview_views(db, [get_record(db, Interview, identifier)])[0]


@router.patch("/interviews/{identifier}")
def interview_patch(
    identifier: UUID,
    values: data.InterviewPatch,
    db: Database,
    actor: InterviewEdit,
    request: Request,
) -> dict[str, Any]:
    row, _ = s.interview_locked(db, identifier, values.version)
    if row.status not in {"SCHEDULED", "RESCHEDULED"}:
        fail("INVALID_INTERVIEW_TRANSITION", "Only a scheduled interview can be edited.", 422)
    previous = row.status
    for key, value in values.model_dump(exclude={"version", "reason"}).items():
        setattr(row, key, value)
    changed(row, actor.user.id)
    s.interview_history(db, row, previous, actor, values.reason)
    s.save(db, row, actor, request, "interview.updated", list(data.InterviewFields.model_fields))
    return s.interview_views(db, [row])[0]


@router.post("/interviews/{identifier}/attend")
def attend(
    identifier: UUID,
    values: data.InterviewAction,
    db: Database,
    actor: InterviewEdit,
    request: Request,
) -> dict[str, Any]:
    return s.interview_views(
        db,
        [
            s.interview_action(
                db, identifier, values.version, "ATTENDED", actor, request, values.reason
            )
        ],
    )[0]


@router.post("/interviews/{identifier}/no-show")
def no_show(
    identifier: UUID,
    values: data.InterviewAction,
    db: Database,
    actor: InterviewEdit,
    request: Request,
) -> dict[str, Any]:
    return s.interview_views(
        db,
        [
            s.interview_action(
                db, identifier, values.version, "NO_SHOW", actor, request, values.reason
            )
        ],
    )[0]


@router.post("/interviews/{identifier}/cancel")
def cancel(
    identifier: UUID,
    values: data.InterviewAction,
    db: Database,
    actor: InterviewEdit,
    request: Request,
) -> dict[str, Any]:
    return s.interview_views(
        db,
        [
            s.interview_action(
                db, identifier, values.version, "CANCELLED", actor, request, values.reason
            )
        ],
    )[0]


@router.post("/interviews/{identifier}/reschedule")
def reschedule(
    identifier: UUID,
    values: data.InterviewReschedule,
    db: Database,
    actor: InterviewEdit,
    request: Request,
) -> dict[str, Any]:
    return s.interview_views(
        db,
        [
            s.interview_action(
                db,
                identifier,
                values.version,
                "RESCHEDULED",
                actor,
                request,
                values.reason,
                scheduled_at=values.scheduled_at,
            )
        ],
    )[0]


@router.post("/interviews/{identifier}/outcome")
def outcome(
    identifier: UUID, values: data.Outcome, db: Database, actor: InterviewEdit, request: Request
) -> dict[str, Any]:
    return s.interview_views(
        db,
        [
            s.interview_action(
                db,
                identifier,
                values.version,
                "COMPLETED",
                actor,
                request,
                values.reason,
                outcome=values.outcome,
            )
        ],
    )[0]


@router.get("/interviews/{identifier}/history")
def interview_history(
    identifier: UUID,
    db: Database,
    actor: InterviewRead,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    get_record(db, Interview, identifier)
    result = s.chronological_page(
        select(InterviewHistory).where(InterviewHistory.interview_id == identifier),
        InterviewHistory,
        InterviewHistory.occurred_at,
        db,
        limit,
        cursor,
    )
    return {
        "items": [
            {
                key: getattr(row, key)
                for key in (
                    "id",
                    "from_status",
                    "to_status",
                    "scheduled_at",
                    "reason",
                    "actor_type",
                    "actor_id",
                    "occurred_at",
                )
            }
            for row in result["rows"]
        ],
        "next_cursor": result["next_cursor"],
    }
