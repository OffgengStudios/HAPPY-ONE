from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.modules.demand.schemas import Text, Version
from app.modules.iam.schemas import Input

Frequency = Literal["DAILY", "WEEKLY", "BIWEEKLY", "MONTHLY"]


class PlacementCreate(Input):
    candidate_vacancy_id: UUID
    candidate_version: int | None = Field(default=None, ge=1)
    expected_start_date: date | None = None
    salary_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    salary_currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "GHS"
    salary_frequency: Frequency | None = None
    payroll_frequency: Frequency | None = None
    payday_rule_json: dict[str, Any] | None = None
    payroll_day: int | None = Field(default=None, ge=1, le=31)
    payroll_cutoff_day: int | None = Field(default=None, ge=1, le=31)
    manual_first_income_date: date | None = None
    exception_reason: Text | None = None
    owner_id: UUID | None = None

    @model_validator(mode="after")
    def schedule(self) -> Self:
        if self.payroll_frequency == "MONTHLY" and self.payroll_day:
            self.payday_rule_json = {
                "day": self.payroll_day,
                "cutoff_day": self.payroll_cutoff_day or self.payroll_day,
            }
        if self.manual_first_income_date and not self.exception_reason:
            raise ValueError("A manual first-income date needs an exception reason.")
        return self


class PlacementPatch(Version):
    expected_start_date: date | None = None
    salary_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    salary_currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "GHS"
    salary_frequency: Frequency | None = None
    payroll_frequency: Frequency | None = None
    payday_rule_json: dict[str, Any] | None = None
    manual_first_income_date: date | None = None
    exception_reason: Text | None = None
    owner_id: UUID | None = None
    reason: Text


class Start(Input):
    version: int = Field(ge=1)
    actual_start_date: date
    manual_first_income_date: date | None = None
    exception_reason: Text | None = None
    notes: Text | None = None


class End(Input):
    version: int = Field(ge=1)
    employment_end_date: date
    reason: Text


class StartOutcome(Input):
    version: int = Field(ge=1)
    outcome: Literal["FAILED_TO_START", "CANCELLED"]
    effective_date: date
    reason: Text


class FirstIncomeConfirm(Input):
    version: int = Field(ge=1)
    actual_income_received_date: date
    amount_received: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    evidence_document_id: UUID | None = None
    notes: Text


class FirstIncomeDelay(Input):
    version: int = Field(ge=1)
    verification_due_date: date
    reason: Text


class FirstIncomeException(FirstIncomeDelay):
    pass


class CorrectConfirmation(Input):
    version: int = Field(ge=1)
    confirmed: bool
    actual_income_received_date: date | None = None
    amount_received: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    reason: Text
