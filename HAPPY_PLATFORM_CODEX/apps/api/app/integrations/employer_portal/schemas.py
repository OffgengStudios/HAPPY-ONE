from datetime import date
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator, model_validator

from app.modules.demand.schemas import Frequency, Money, RequirementFields, normalize_phone

Short = Annotated[str, Field(min_length=1, max_length=200)]
Text = Annotated[str, Field(min_length=1, max_length=5000)]


class PortalVacancy(BaseModel):
    model_config = {"populate_by_name": True, "extra": "forbid"}
    vacancy_id: str | None = Field(default=None, max_length=200, alias="vacancyId")
    job_title: Short = Field(alias="jobTitle")
    location: Short
    employment_type: Short = Field(alias="employmentType")
    openings: int = Field(default=1, ge=1, le=1000)
    compensation: Short | None = None
    description: Text | None = None
    salary_min: Money | None = None
    salary_max: Money | None = None
    salary_frequency: Frequency | None = None
    work_days: Annotated[str, Field(max_length=150)] | None = None
    work_hours: Annotated[str, Field(max_length=150)] | None = None
    accommodation: bool | None = None
    benefits: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(
        default_factory=list, max_length=20
    )
    deadline: date | None = None
    requirements: list[RequirementFields] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def salary(self) -> Self:
        if self.salary_min is not None or self.salary_max is not None:
            if not self.salary_frequency:
                raise ValueError("Salary requires a frequency.")
            if (
                self.salary_min is not None
                and self.salary_max is not None
                and self.salary_min > self.salary_max
            ):
                raise ValueError("Check the salary range.")
        return self


class PortalSubmission(BaseModel):
    submission_id: str = Field(min_length=1, max_length=200, alias="submissionId")
    reference_number: str | None = Field(default=None, max_length=80, alias="referenceNumber")
    company_name: Short = Field(alias="companyName")
    sector: Short | None = None
    company_size: Short | None = Field(default=None, alias="companySize")
    region: Short | None = None
    city: Short | None = None
    website: HttpUrl | None = None
    contact_name: Short = Field(alias="contactName")
    contact_role: Short | None = Field(default=None, alias="contactRole")
    contact_phone: str = Field(min_length=1, max_length=50, alias="contactPhone")
    contact_email: EmailStr = Field(alias="contactEmail")
    consent_agreement: bool = Field(alias="consentAgreement")
    consent_contact: bool = Field(alias="consentContact")
    signature_file_id: str = Field(min_length=1, max_length=200, alias="signatureFileId")
    vacancies: list[PortalVacancy] = Field(min_length=1, max_length=20)
    document_ids: list[str] = Field(default_factory=list, max_length=10, alias="documentIds")
    industry: Annotated[str, Field(max_length=60)] | None = None
    district: Annotated[str, Field(max_length=60)] | None = None
    address: Text | None = None
    partnership_type: Literal["TRAINING", "RECRUITMENT", "COMBINED"] = "RECRUITMENT"
    partnership_start_date: date | None = None

    @field_validator("contact_phone")
    @classmethod
    def phone(cls, value: str) -> str:
        normalize_phone(value)
        return value

    @model_validator(mode="after")
    def consent(self) -> Self:
        if not self.consent_agreement or not self.consent_contact:
            raise ValueError("Both employer consent confirmations are required.")
        return self

    model_config = {"populate_by_name": True}


class ConvertSubmission(BaseModel):
    version: int = Field(ge=1)
    existing_organization_id: UUID | None = None
    mou_required: bool = True
    reason: str = Field(min_length=1, max_length=1000)


class ReviewSubmission(BaseModel):
    version: int = Field(ge=1)
    decision: Literal["REJECT", "ARCHIVE"]
    reason: str = Field(min_length=1, max_length=1000)
