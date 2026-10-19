from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.modules.demand.schemas import Priority, Text, Version
from app.modules.iam.schemas import Input

Stage = Literal[
    "POTENTIAL_MATCH",
    "RECRUITER_REVIEW",
    "PRE_SCREEN",
    "QUALIFIED",
    "SUBMITTED",
    "INTERVIEW",
    "EMPLOYER_DECISION",
    "SELECTED",
    "STARTED",
    "AWAITING_FIRST_INCOME",
    "CONFIRMED_PLACEMENT",
    "NOT_INTERESTED",
    "UNREACHABLE",
    "NO_SHOW",
    "REJECTED",
    "WITHDRAWN",
    "SALARY_DECLINED",
    "LOCATION_DECLINED",
    "FAILED_TO_START",
    "EMPLOYER_CANCELLED",
]
InterviewState = Literal[
    "SCHEDULED", "ATTENDED", "NO_SHOW", "RESCHEDULED", "CANCELLED", "COMPLETED"
]
InterviewOutcome = Literal["PASSED", "REJECTED", "PENDING_EMPLOYER_DECISION", "NOT_APPLICABLE"]


class CandidateFields(Input):
    owner_id: UUID | None = None
    priority: Priority = "NORMAL"
    next_action: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    next_action_due_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def due(self) -> Self:
        if self.next_action_due_at and not self.next_action:
            raise ValueError("A due date needs a next action.")
        return self


class CandidateCreate(CandidateFields):
    participant_id: UUID
    vacancy_id: UUID
    source: Literal["STAFF", "PARTICIPANT", "EMPLOYER", "REFERRAL"] = "STAFF"


class CandidatePatch(CandidateFields, Version):
    reason: Text


class Transition(Version):
    to_status: Stage
    reason: Text | None = None


class CandidateVersion(Version):
    id: UUID


class BulkTransition(Input):
    candidates: list[CandidateVersion] = Field(min_length=1, max_length=25)
    to_status: Stage
    reason: Text | None = None

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({row.id for row in self.candidates}) != len(self.candidates):
            raise ValueError("Choose each candidate once.")
        return self


class ScreeningInput(Version):
    result: Literal["QUALIFIED", "NOT_QUALIFIED", "FOLLOW_UP"]
    participant_interested: bool
    availability_confirmed: bool
    salary_accepted: bool | None = None
    location_accepted: bool | None = None
    notes: Text | None = None

    @model_validator(mode="after")
    def qualified(self) -> Self:
        if self.result == "QUALIFIED" and (
            not self.participant_interested
            or not self.availability_confirmed
            or self.salary_accepted is False
            or self.location_accepted is False
        ):
            raise ValueError(
                "Qualified screening requires confirmed interest and availability "
                "without declined terms."
            )
        return self


class Decision(Version):
    decision: Literal["SELECTED", "REJECTED", "PENDING"]
    reason: Text


class InterviewFields(Input):
    scheduled_at: AwareDatetime
    timezone: Literal["Africa/Accra"] = "Africa/Accra"
    format: Literal["IN_PERSON", "PHONE", "VIDEO"]
    location_or_link: Annotated[str, Field(min_length=1, max_length=1000)]
    notes: Text | None = None


class InterviewCreate(InterviewFields):
    candidate_vacancy_id: UUID
    candidate_version: int = Field(ge=1)


class InterviewPatch(InterviewFields, Version):
    reason: Text


class InterviewAction(Version):
    reason: Text


class InterviewReschedule(InterviewAction):
    scheduled_at: AwareDatetime


class Outcome(InterviewAction):
    outcome: InterviewOutcome


class TimeCursor(Input):
    id: UUID
    at: AwareDatetime
