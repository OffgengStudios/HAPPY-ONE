from datetime import datetime
from typing import Any, get_args
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.provenance import Provenance
from app.modules.demand.models import Record
from app.modules.iam.models import now
from app.modules.matching.schemas import Stage

TERMINAL = {
    "NOT_INTERESTED",
    "UNREACHABLE",
    "NO_SHOW",
    "REJECTED",
    "WITHDRAWN",
    "SALARY_DECLINED",
    "LOCATION_DECLINED",
    "FAILED_TO_START",
    "EMPLOYER_CANCELLED",
}
STAGES = get_args(Stage)
STATUS_CHECK = "status IN (" + ",".join(repr(value) for value in STAGES) + ")"
ACTIVE_PAIR = (
    "archived_at IS NULL AND status NOT IN ("
    + ",".join(repr(value) for value in sorted(TERMINAL))
    + ")"
)
ACTOR_CHECK = "actor_type IN ('USER','PARTICIPANT','EMPLOYER','SYSTEM','INTEGRATION')"
ACTOR_ID_CHECK = (
    "(actor_type IN ('USER','PARTICIPANT','EMPLOYER') AND actor_id IS NOT NULL "
    "AND actor_id ~ '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    "[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$') OR "
    "(actor_type='SYSTEM' AND (actor_id IS NULL OR actor_id ~ '^[A-Z][A-Z0-9_]{0,99}$')) OR "
    "(actor_type='INTEGRATION' AND actor_id IS NOT NULL "
    "AND actor_id ~ '^[A-Z][A-Z0-9_]{0,99}$')"
)


class CandidateVacancy(Record, Base):
    __tablename__ = "candidate_vacancies"
    __table_args__ = (
        CheckConstraint(STATUS_CHECK, name="ck_candidate_status"),
        CheckConstraint("priority IN ('NORMAL','HIGH','URGENT')", name="ck_candidate_priority"),
        CheckConstraint(
            "source IN ('STAFF','PARTICIPANT','EMPLOYER','REFERRAL')", name="ck_candidate_source"
        ),
        CheckConstraint(
            "status NOT IN ('SUBMITTED','INTERVIEW','EMPLOYER_DECISION','SELECTED','STARTED',"
            "'AWAITING_FIRST_INCOME','CONFIRMED_PLACEMENT') OR submitted_at IS NOT NULL",
            name="ck_candidate_submission",
        ),
        CheckConstraint(
            "status NOT IN ('SELECTED','STARTED','AWAITING_FIRST_INCOME','CONFIRMED_PLACEMENT') "
            "OR selected_at IS NOT NULL",
            name="ck_candidate_selection",
        ),
        CheckConstraint(
            "next_action_due_at IS NULL OR next_action IS NOT NULL",
            name="ck_candidate_next_action_due",
        ),
        Index(
            "uq_active_candidate_vacancy",
            "participant_id",
            "vacancy_id",
            unique=True,
            postgresql_where=text(ACTIVE_PAIR),
        ),
        Index("ix_candidate_owner_status", "owner_id", "status"),
    )
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("participants.id"), index=True)
    vacancy_id: Mapped[UUID] = mapped_column(ForeignKey("vacancies.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="POTENTIAL_MATCH", index=True)
    owner_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    owner_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(20), default="STAFF")
    priority: Mapped[str] = mapped_column(String(15), default="NORMAL")
    next_action: Mapped[str | None] = mapped_column(String(500))
    next_action_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pre_screen_result: Mapped[str | None] = mapped_column(String(30))
    match_strength: Mapped[str | None] = mapped_column(String(20))
    match_explanation_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_reason: Mapped[str | None] = mapped_column(String(30))
    closed_note: Mapped[str | None] = mapped_column(Text)


class CandidateHistory(Base):
    __tablename__ = "candidate_status_history"
    __table_args__ = (
        CheckConstraint(ACTOR_CHECK, name="ck_candidate_history_actor"),
        CheckConstraint(ACTOR_ID_CHECK, name="ck_candidate_history_actor_id"),
        CheckConstraint(
            "to_status IN (" + ",".join(repr(value) for value in STAGES) + ")",
            name="ck_candidate_history_to_status",
        ),
        CheckConstraint(
            "from_status IS NULL OR from_status IN ("
            + ",".join(repr(value) for value in STAGES)
            + ")",
            name="ck_candidate_history_from_status",
        ),
        Index("ix_candidate_history_chronology", "candidate_vacancy_id", "occurred_at", "id"),
        Index("ix_candidate_history_stage_occurred", "to_status", "occurred_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    candidate_vacancy_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_vacancies.id"), index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text)
    actor_type: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[str | None] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Screening(Provenance, Base):
    __tablename__ = "candidate_screenings"
    __table_args__ = (
        CheckConstraint(
            "result IN ('QUALIFIED','NOT_QUALIFIED','FOLLOW_UP')", name="ck_screening_result"
        ),
        CheckConstraint(
            "result <> 'QUALIFIED' OR (participant_interested AND availability_confirmed "
            "AND salary_accepted IS NOT FALSE AND location_accepted IS NOT FALSE)",
            name="ck_screening_qualified_evidence",
        ),
        Index("ix_screening_chronology", "candidate_vacancy_id", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    candidate_vacancy_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_vacancies.id"), index=True
    )
    result: Mapped[str] = mapped_column(String(30))
    participant_interested: Mapped[bool] = mapped_column(Boolean)
    availability_confirmed: Mapped[bool] = mapped_column(Boolean)
    salary_accepted: Mapped[bool | None] = mapped_column(Boolean)
    location_accepted: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EmployerDecision(Provenance, Base):
    __tablename__ = "employer_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('SELECTED','REJECTED','PENDING')", name="ck_employer_decision"
        ),
        Index("ix_employer_decision_chronology", "candidate_vacancy_id", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    candidate_vacancy_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_vacancies.id"), index=True
    )
    decision: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Interview(Record, Base):
    __tablename__ = "interviews"
    __table_args__ = (
        CheckConstraint(
            "status IN ('SCHEDULED','ATTENDED','NO_SHOW','RESCHEDULED','CANCELLED','COMPLETED')",
            name="ck_interview_status",
        ),
        CheckConstraint("format IN ('IN_PERSON','PHONE','VIDEO')", name="ck_interview_format"),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('PASSED','REJECTED','PENDING_EMPLOYER_DECISION',"
            "'NOT_APPLICABLE')",
            name="ck_interview_outcome",
        ),
        CheckConstraint("timezone='Africa/Accra'", name="ck_interview_timezone"),
        CheckConstraint(
            "status <> 'COMPLETED' OR outcome IS NOT NULL",
            name="ck_interview_completed_outcome",
        ),
    )
    candidate_vacancy_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_vacancies.id"), index=True
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Africa/Accra")
    format: Mapped[str] = mapped_column(String(20))
    location_or_link: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default="SCHEDULED")
    outcome: Mapped[str | None] = mapped_column(String(30))
    notes: Mapped[str | None] = mapped_column(Text)


class InterviewHistory(Base):
    __tablename__ = "interview_history"
    __table_args__ = (
        CheckConstraint(ACTOR_CHECK, name="ck_interview_history_actor"),
        CheckConstraint(ACTOR_ID_CHECK, name="ck_interview_history_actor_id"),
        CheckConstraint(
            "to_status IN ('SCHEDULED','ATTENDED','NO_SHOW','RESCHEDULED','CANCELLED','COMPLETED')",
            name="ck_interview_history_to_status",
        ),
        CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('SCHEDULED','ATTENDED','NO_SHOW','RESCHEDULED','CANCELLED','COMPLETED')",
            name="ck_interview_history_from_status",
        ),
        Index("ix_interview_history_chronology", "interview_id", "occurred_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    interview_id: Mapped[UUID] = mapped_column(ForeignKey("interviews.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)
    actor_type: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[str | None] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
