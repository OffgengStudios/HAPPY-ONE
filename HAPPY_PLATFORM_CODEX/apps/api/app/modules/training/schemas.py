from datetime import date
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.modules.demand.schemas import Text, Version

Short = Annotated[str, Field(min_length=1, max_length=200)]
Code = Annotated[str, Field(min_length=1, max_length=60, pattern=r"^[A-Z][A-Z0-9_]*$")]


class TrainingFields(BaseModel):
    title: Short
    training_type: Code
    partner_organization_id: UUID | None = None
    trainer_type: Literal["INTERNAL", "EXTERNAL_PARTNER"]
    mode: Literal["IN_PERSON", "VIRTUAL", "HYBRID"]
    start_date: date
    end_date: date | None = None
    location_region_code: Code | None = None
    location_district_code: Code | None = None
    location_community: Short | None = None
    location_text: Text | None = None
    virtual_platform: Short | None = None
    modules_json: list[Short] = Field(default_factory=list, max_length=100)
    agriculture_sector: Annotated[str, Field(min_length=1, max_length=60)] | None = None
    status: Literal["DRAFT", "PLANNED", "IN_PROGRESS", "COMPLETED", "CANCELLED"] = "DRAFT"

    @model_validator(mode="after")
    def valid_dates_and_mode(self) -> Self:
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("End date cannot precede start date.")
        if self.mode in {"VIRTUAL", "HYBRID"} and not self.virtual_platform:
            raise ValueError("Virtual and hybrid training require a virtual platform.")
        if self.trainer_type == "EXTERNAL_PARTNER" and not self.partner_organization_id:
            raise ValueError("External partner training requires a partner organization.")
        return self


class TrainingCreate(TrainingFields):
    pass


class TrainingUpdate(TrainingFields, Version):
    pass


class AttendanceCreate(BaseModel):
    participant_ids: list[UUID] = Field(min_length=1, max_length=500)
    attendance_status: Literal["PRESENT", "ABSENT", "LATE", "EXCUSED"] = "PRESENT"
    completion_status: Literal["NOT_STARTED", "IN_PROGRESS", "COMPLETED", "NOT_COMPLETED"] = (
        "NOT_STARTED"
    )
    notes: Text | None = None


class AttendanceUpdate(Version):
    received_modules: list[Short] = Field(default_factory=list, max_length=100)
    completed_modules: list[Short] = Field(default_factory=list, max_length=100)
    attendance_status: Literal["PRESENT", "ABSENT", "LATE", "EXCUSED"]
    completion_status: Literal["NOT_STARTED", "IN_PROGRESS", "COMPLETED", "NOT_COMPLETED"]
    notes: Text | None = None

    @model_validator(mode="after")
    def modules(self) -> Self:
        if not set(self.completed_modules) <= set(self.received_modules):
            raise ValueError("Completed modules must also be recorded as received.")
        return self


class CertificateWrite(Version):
    document_id: UUID
