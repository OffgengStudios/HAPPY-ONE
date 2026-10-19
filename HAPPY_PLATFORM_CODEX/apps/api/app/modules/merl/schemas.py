from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.modules.demand.schemas import Text, Version

Short = Annotated[str, Field(min_length=1, max_length=200)]
Code = Annotated[str, Field(min_length=1, max_length=60, pattern=r"^[A-Z][A-Z0-9_]*$")]


class FollowUpCreate(BaseModel):
    placement_id: UUID
    follow_up_type: Code | None = None
    scheduled_for: date | None = None
    template_id: UUID | None = None
    owner_id: UUID | None = None

    @model_validator(mode="after")
    def schedule_source(self) -> Self:
        if (self.scheduled_for is None) == (self.template_id is None):
            raise ValueError("Choose either a manual date or one follow-up template.")
        if self.scheduled_for is not None and self.follow_up_type is None:
            raise ValueError("Manual follow-ups require a follow-up type.")
        return self


class FollowUpComplete(Version):
    contact_result: Literal["REACHED", "NOT_REACHED", "DECLINED", "RESCHEDULED"]
    notes: Text


class FollowUpCancel(Version):
    reason: Text


class OutcomeFields(BaseModel):
    as_of_date: date
    currently_working: bool
    current_employer: Short | None = None
    current_role: Short | None = None
    current_income_amount: Decimal | None = Field(default=None, ge=0)
    income_frequency: Literal["DAILY", "WEEKLY", "BIWEEKLY", "MONTHLY", "OTHER"] | None = None
    job_satisfaction: int | None = Field(default=None, ge=1, le=5)
    challenges_text: Text | None = None
    progress_text: Text | None = None
    skills_gained_text: Text | None = None
    household_community_effects_text: Text | None = None
    support_needed_text: Text | None = None
    impact_story_potential: bool = False

    @model_validator(mode="after")
    def income(self) -> Self:
        if self.current_income_amount is not None and not self.income_frequency:
            raise ValueError("Current income needs a frequency.")
        return self


class OutcomeCreate(OutcomeFields):
    placement_id: UUID
    follow_up_id: UUID | None = None


class OutcomeUpdate(OutcomeFields, Version):
    reason: Text


class IssueCreate(BaseModel):
    entity_type: Literal["PARTICIPANT", "PLACEMENT", "FOLLOW_UP", "OUTCOME"]
    entity_id: UUID
    issue_type: Code
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    description: Text
    owner_id: UUID | None = None


class IssueAssign(Version):
    owner_id: UUID


class IssueResolve(Version):
    resolution: Literal["RESOLVED", "DISMISSED"]
    notes: Text


class TemplateWrite(BaseModel):
    template_code: Annotated[str, Field(min_length=1, max_length=40, pattern=r"^[A-Z][A-Z0-9_]*$")]
    name: Annotated[str, Field(min_length=1, max_length=150)]
    follow_up_type: Code
    anchor: Literal["ACTUAL_START", "CONFIRMED"]
    offset_days: int = Field(ge=0, le=3650)
    required_questions: list[str] = Field(default_factory=list, max_length=50)
    owner_role_code: Annotated[str, Field(min_length=1, max_length=40)] | None = None
    is_active: bool = True


class TemplateUpdate(TemplateWrite, Version):
    pass
