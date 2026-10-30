import re
from datetime import date
from typing import Literal, Self
from uuid import UUID

from pydantic import EmailStr, Field, HttpUrl, SecretStr, field_validator, model_validator

from app.integrations.employer_portal.schemas import PortalVacancy
from app.modules.demand.schemas import normalize_phone
from app.modules.iam.schemas import Input
from app.modules.supply import schemas as supply


class PublicConsent(Input):
    accepted: Literal[True]
    notice_version: str = Field(min_length=1, max_length=100)


class PublicEmployment(supply.EmploymentWrite):
    version: Literal[1] = 1

    @model_validator(mode="after")
    def self_reported(self) -> Self:
        if any(
            skill.verified or skill.source not in {None, "SELF_REPORTED"} for skill in self.skills
        ):
            raise ValueError("Only self-reported, unverified skills may be submitted.")
        return self


class PublicDemographics(supply.Demographics):
    version: Literal[1] = 1


class PublicSensitive(supply.SensitiveWrite):
    version: Literal[1] = 1


class PublicContact(supply.Contact):
    @field_validator("phone_raw")
    @classmethod
    def ghana_phone(cls, value: str) -> str:
        canonical = normalize_phone(value)
        if not canonical or not re.fullmatch(r"\+233[0-9]{9}", canonical):
            raise ValueError("Enter a valid Ghana phone number.")
        return value


class PublicIdentity(supply.IdentityWrite):
    version: Literal[1] = 1
    government_id_type: Literal["GHANA_CARD"] = "GHANA_CARD"

    @field_validator("government_id")
    @classmethod
    def ghana_card(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value().strip().upper()
        if not re.fullmatch(r"GHA-[0-9]{9}-[0-9]", raw):
            raise ValueError("Check the Ghana Card format.")
        return value.__class__(raw)


class ParticipantSubmission(Input):
    submission_id: UUID
    basic: supply.Basic
    contact: PublicContact
    demographics: PublicDemographics | None = None
    education: list[supply.EducationFields] = Field(default_factory=list, max_length=30)
    employment: PublicEmployment | None = None
    sensitive: PublicSensitive | None = None
    identity: PublicIdentity | None = None
    training_interests: list[supply.TrainingInterest] = Field(default_factory=list, max_length=2)
    implementing_partner: str | None = Field(default=None, max_length=150)
    supplemental: dict[str, str] = Field(default_factory=dict, max_length=25)
    training_summary: str | None = Field(default=None, max_length=5000)
    consent: PublicConsent
    reviewed: Literal[True]
    website: Literal[""] = ""  # Honeypot; never used as participant data.

    @model_validator(mode="after")
    def supplemental_fields(self) -> Self:
        if len(set(self.training_interests)) != len(self.training_interests):
            raise ValueError("Select each training interest once.")
        allowed = {
            "preferredName",
            "participantTypeSupport",
            "secondaryPhone",
            "referralPhone",
            "referralRelationship",
            "guarantorName",
            "homeAddress",
            "baselineEmploymentType",
            "activeStudent",
            "hostCommunity",
            "workLocationStatus",
            "nationalityOrigin",
        }
        if not set(self.supplemental) <= allowed or any(
            len(value) > 500 for value in self.supplemental.values()
        ):
            raise ValueError("Check the supplementary self-reported fields.")
        return self


class IntakeReview(Input):
    decision: Literal["REJECT"]
    reason: str = Field(min_length=1, max_length=1000)


class DuplicateResolution(Input):
    existing_participant_id: UUID
    reason: str = Field(min_length=1, max_length=1000)


class EmployerDocument(Input):
    kind: Literal["MOU", "AGREEMENT", "JD", "SUPPORTING"]
    vacancy_index: int | None = Field(default=None, ge=0, le=19)


class EmployerSubmission(Input):
    submission_id: UUID
    company_name: str = Field(min_length=1, max_length=200)
    sector: str | None = Field(default=None, max_length=60)
    industry: str | None = Field(default=None, max_length=60)
    region: str | None = Field(default=None, max_length=60)
    district: str | None = Field(default=None, max_length=60)
    city: str | None = Field(default=None, max_length=150)
    address: str | None = Field(default=None, max_length=5000)
    website: HttpUrl | None = None
    contact_name: str = Field(min_length=1, max_length=150)
    contact_role: str | None = Field(default=None, max_length=150)
    contact_phone: str = Field(min_length=1, max_length=50)
    contact_email: EmailStr
    partnership_type: Literal["TRAINING", "RECRUITMENT", "COMBINED"] = "RECRUITMENT"
    partnership_start_date: date | None = None
    consent_agreement: Literal[True]
    consent_contact: Literal[True]
    vacancies: list[PortalVacancy] = Field(min_length=1, max_length=20)
    documents: list[EmployerDocument] = Field(default_factory=list, max_length=5)
    company_fax: Literal[""] = ""  # Honeypot.

    @field_validator("contact_phone")
    @classmethod
    def phone(cls, value: str) -> str:
        normalize_phone(value)
        return value

    @model_validator(mode="after")
    def document_targets(self) -> Self:
        for item in self.documents:
            if item.kind == "JD" and (
                item.vacancy_index is None or item.vacancy_index >= len(self.vacancies)
            ):
                raise ValueError("A job description needs its submitted vacancy.")
        return self
