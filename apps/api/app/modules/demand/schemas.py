from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self
from uuid import UUID

import phonenumbers
from pydantic import AwareDatetime, EmailStr, Field, HttpUrl, field_validator, model_validator

from app.modules.iam.schemas import Input

Name = Annotated[str, Field(min_length=1, max_length=200)]
Short = Annotated[str, Field(min_length=1, max_length=150)]
Code = Annotated[str, Field(min_length=1, max_length=60)]
Text = Annotated[str, Field(min_length=1, max_length=5000)]
Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False)]
Priority = Literal["NORMAL", "HIGH", "URGENT"]
Frequency = Literal["HOURLY", "DAILY", "WEEKLY", "BIWEEKLY", "MONTHLY", "OTHER"]


def normalized_name(value: str) -> str:
    return " ".join(value.casefold().split())


def normalize_phone(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        number = phonenumbers.parse(value, "GH")
        if not phonenumbers.is_valid_number(number):
            raise ValueError("Enter a valid telephone number.")
        return str(phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164))
    except phonenumbers.NumberParseException:
        raise ValueError("Enter a valid telephone number.") from None


class Version(Input):
    version: int = Field(ge=1)


class OrganizationFields(Input):
    name: Name
    organization_type: Annotated[str, Field(min_length=1, max_length=60)]
    industry_code: Code | None = None
    sector_code: Code | None = None
    region_code: Code | None = None
    district_code: Code | None = None
    community: Short | None = None
    address_text: Text | None = None
    website: Annotated[HttpUrl, Field(max_length=500)] | None = None
    relationship_owner_id: UUID | None = None


class OrganizationCreate(OrganizationFields):
    mou_required: bool
    duplicate_acknowledged: bool = False


class OrganizationPatch(OrganizationFields, Version):
    duplicate_acknowledged: bool = False


class ContactFields(Input):
    full_name: Short
    job_title: Short | None = None
    phone_raw: Annotated[str, Field(min_length=1, max_length=50)] | None = None
    email: EmailStr | None = None
    is_primary: bool = False
    is_active: bool = True
    notes: Text | None = None

    @field_validator("phone_raw")
    @classmethod
    def phone(cls, value: str | None) -> str | None:
        normalize_phone(value)
        return value


class ContactPatch(ContactFields, Version):
    pass


class PartnershipFields(Input):
    partnership_type: Literal["TRAINING", "RECRUITMENT", "COMBINED"] = "RECRUITMENT"
    start_date: date = Field(default_factory=date.today)
    end_date: date | None = None
    mou_required: bool
    priority: Priority = "NORMAL"
    mou_sent_at: AwareDatetime | None = None
    mou_signed_at: AwareDatetime | None = None
    owner_id: UUID | None = None
    next_action: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    next_action_due_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def dates(self) -> Self:
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("The partnership end date cannot precede its start date.")
        if self.mou_sent_at and self.mou_signed_at and self.mou_signed_at < self.mou_sent_at:
            raise ValueError("The signed date cannot precede the sent date.")
        if self.next_action_due_at and not self.next_action:
            raise ValueError("A due date needs a next action.")
        return self


class PartnershipPatch(PartnershipFields, Version):
    reason: Text | None = None


class Transition(Version):
    to_status: Annotated[str, Field(min_length=1, max_length=30)]
    reason: Text | None = None


class VacancyFields(Input):
    title: Name
    priority: Priority = "NORMAL"
    description: Text | None = None
    location_region_code: Code | None = None
    location_district_code: Code | None = None
    location_community: Short | None = None
    location_directions: Text | None = None
    salary_min: Money | None = None
    salary_max: Money | None = None
    salary_currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "GHS"
    salary_frequency: Frequency | None = None
    work_days_text: Short | None = None
    work_hours_text: Short | None = None
    accommodation_available: bool | None = None
    required_headcount: int = Field(gt=0, le=1000000, strict=True)
    owner_id: UUID | None = None
    demand_owner_id: UUID | None = None

    @model_validator(mode="after")
    def salary(self) -> Self:
        if self.salary_min is not None and self.salary_max is not None:
            if self.salary_min > self.salary_max:
                raise ValueError("Minimum salary cannot exceed maximum salary.")
        return self


class VacancyCreate(VacancyFields):
    organization_id: UUID


class VacancyPatch(VacancyFields, Version):
    reason: Text


class VacancyTransition(Transition):
    closure_reason: (
        Literal[
            "FULLY_FILLED",
            "EMPLOYER_CANCELLED",
            "EMPLOYER_UNAVAILABLE",
            "EMPLOYER_NO_RESPONSE",
            "REQUIREMENTS_CHANGED",
            "RECRUITMENT_UNSUCCESSFUL",
            "OTHER",
        ]
        | None
    ) = None
    closure_note: Text | None = None


class RequirementFields(Input):
    criterion_type: Annotated[str, Field(min_length=1, max_length=60)]
    criterion_key: Annotated[str, Field(min_length=1, max_length=100)]
    operator: Literal["EQ", "IN", "GTE", "LTE"]
    value_json: str | bool | int | float | list[str | bool | int | float]
    is_required: bool = True
    weight: Annotated[Decimal, Field(ge=0, le=999999, decimal_places=2, allow_inf_nan=False)] = (
        Decimal(1)
    )
    display_order: int = Field(ge=0, le=10000)

    @model_validator(mode="after")
    def criterion(self) -> Self:
        import math

        values = self.value_json if isinstance(self.value_json, list) else [self.value_json]
        if len(values) > 100 or any(isinstance(v, float) and not math.isfinite(v) for v in values):
            raise ValueError("Criterion values must be finite and bounded.")
        if any(isinstance(v, str) and (not v.strip() or len(v) > 500) for v in values):
            raise ValueError("Criterion text must contain 1 to 500 characters.")
        if self.operator == "IN" and (not isinstance(self.value_json, list) or not values):
            raise ValueError("IN needs a non-empty list.")
        if self.operator != "IN" and isinstance(self.value_json, list):
            raise ValueError("This operator needs a scalar value.")
        if self.operator in {"GTE", "LTE"} and (
            isinstance(self.value_json, bool) or not isinstance(self.value_json, int | float)
        ):
            raise ValueError("Numeric comparison needs a number.")
        return self


class RequirementWrite(RequirementFields, Version):
    reason: Text


class Archive(Version):
    reason: Text


def json_value(value: Any) -> Any:
    if isinstance(value, UUID | Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value
