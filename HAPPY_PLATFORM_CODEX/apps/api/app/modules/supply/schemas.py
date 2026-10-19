from datetime import date
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, EmailStr, Field, SecretStr, field_validator, model_validator

from app.modules.demand.schemas import Frequency, Money, Priority, Text, Version, normalize_phone
from app.modules.iam.models import now
from app.modules.iam.schemas import Input

Name = Annotated[str, Field(min_length=1, max_length=100)]
Short = Annotated[str, Field(min_length=1, max_length=150)]
Code = Annotated[str, Field(min_length=1, max_length=60)]
OnboardingStatus = Literal["NOT_STARTED", "IN_PROGRESS", "COMPLETE", "BLOCKED", "WITHDRAWN"]
ReadinessStatus = Literal["NOT_ASSESSED", "DEVELOPING", "JOB_READY", "NOT_JOB_READY"]
AvailabilityStatus = Literal["UNKNOWN", "AVAILABLE", "TEMPORARILY_UNAVAILABLE", "UNAVAILABLE"]
SECTIONS = (
    "basic",
    "contact",
    "demographics",
    "education",
    "employment",
    "training",
    "consent",
    "cv",
    "review",
)


class Basic(Input):
    first_name: Name
    surname: Name
    other_names: Name | None = None


class Contact(Input):
    phone_raw: Annotated[str, Field(min_length=1, max_length=50)]
    email: EmailStr | None = None
    region_code: Code | None = None
    district_code: Code | None = None
    community: Short
    directions: Text | None = None
    location_status: Code | None = None

    @field_validator("phone_raw")
    @classmethod
    def phone(cls, value: str) -> str:
        normalize_phone(value)
        return value


class Intake(Basic, Contact):
    assigned_user_id: UUID | None = None
    source_type: Code | None = None
    source_detail: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    duplicate_acknowledged: bool = False
    implementing_partner: Short | None = None


class Assignment(Version):
    assigned_user_id: UUID | None = None
    priority: Priority = "NORMAL"
    next_action: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    next_action_due_at: AwareDatetime | None = None
    reason: Text

    @model_validator(mode="after")
    def due(self) -> Self:
        if self.next_action_due_at and not self.next_action:
            raise ValueError("A due date needs a next action.")
        return self


class BasicWrite(Basic, Version):
    duplicate_acknowledged: bool = False
    implementing_partner: Short | None = None


class ContactWrite(Contact, Version):
    duplicate_acknowledged: bool = False


class Demographics(Version):
    date_of_birth: date | None = None
    sex: Code | None = None
    nationality: Code | None = None

    @field_validator("date_of_birth")
    @classmethod
    def birthday(cls, value: date | None) -> date | None:
        if value and (value > now().date() or value.year < 1900):
            raise ValueError("Enter a valid date of birth.")
        return value


class SensitiveWrite(Version):
    refugee_status: Code | None = None
    displacement_status: Code | None = None
    displacement_reason: Text | None = None
    original_community: Short | None = None
    host_community: Short | None = None
    disability_status: Code | None = None
    disability_specify: Text | None = None
    current_income_amount: Money | None = None
    income_frequency: Frequency | None = None

    @model_validator(mode="after")
    def income(self) -> Self:
        if self.current_income_amount is not None and not self.income_frequency:
            raise ValueError("Income needs a frequency.")
        return self


class IdentityWrite(Version):
    government_id_type: Literal["GHANA_CARD", "VOTER_ID"]
    government_id: SecretStr

    @field_validator("government_id")
    @classmethod
    def identity(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if (
            not 5 <= len(raw) <= 80
            or not raw.isascii()
            or not all(c.isalnum() or c in "- " for c in raw)
        ):
            raise ValueError("Check the identity reference.")
        return value


class EducationFields(Input):
    education_level: Annotated[str, Field(min_length=1, max_length=100)]
    institution: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    field_of_study: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    start_year: int | None = Field(default=None, ge=1900, le=2100)
    end_year: int | None = Field(default=None, ge=1900, le=2100)
    is_highest: bool = False

    @model_validator(mode="after")
    def years(self) -> Self:
        if self.start_year and self.end_year and self.start_year > self.end_year:
            raise ValueError("Education end cannot precede its start.")
        return self


class ExperienceFields(Input):
    employer_name: Annotated[str, Field(min_length=1, max_length=200)]
    role_title: Annotated[str, Field(min_length=1, max_length=200)]
    sector: Code | None = None
    start_date: date
    end_date: date | None = None
    description: Text | None = None

    @model_validator(mode="after")
    def dates(self) -> Self:
        if self.start_date > now().date() or (self.end_date and self.end_date < self.start_date):
            raise ValueError("Check employment dates.")
        return self


class SkillFields(Input):
    skill_name: Short
    skill_code: Code | None = None
    level: Code | None = None
    source: Name | None = None
    verified: bool = False


class EducationWrite(Version):
    items: list[EducationFields] = Field(max_length=30)


class EmploymentWrite(Version):
    employment_status: Code | None = None
    current_occupation: Short | None = None
    experience: list[ExperienceFields] = Field(default_factory=list, max_length=30)
    skills: list[SkillFields] = Field(default_factory=list, max_length=100)
    sector_code: Code | None = None
    industry_code: Code | None = None
    job_type: Code | None = None
    job_role: Short | None = None
    work_region_code: Code | None = None
    work_district_code: Code | None = None
    work_community: Short | None = None


class TrainingWrite(Version):
    training_summary: Text | None = None


class ReviewWrite(Version):
    reviewed: Literal[True]


class ConsentWrite(Version):
    consent_type: Literal["PROGRAMME", "MARKETING", "PUBLICATION"]
    consented_at: AwareDatetime
    method: Literal["WRITTEN", "VERBAL", "DIGITAL", "STAFF_RECORDED"]
    privacy_notice_version: Annotated[str, Field(min_length=1, max_length=100)]
    participant_agreed: Literal[True]

    @field_validator("consented_at")
    @classmethod
    def time(cls, value: AwareDatetime) -> AwareDatetime:
        if value > now():
            raise ValueError("Consent cannot be future-dated.")
        return value


class Complete(Version):
    completion_mode: Literal["SELF_REPORTED", "STAFF_ASSISTED"]


class StatusWrite(Version):
    readiness_status: ReadinessStatus
    availability_status: AvailabilityStatus
    reason: Text


class OnboardingState(Version):
    to_status: Literal["IN_PROGRESS", "BLOCKED", "WITHDRAWN"]
    reason: Text


class CVWaiver(Version):
    reason: Text
