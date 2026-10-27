from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.modules.demand.models import Record


class Person(Record, Base):
    __tablename__ = "people"
    __table_args__ = (UniqueConstraint("government_id_hash", name="uq_person_government_id_hash"),)
    first_name: Mapped[str] = mapped_column(String(100))
    surname: Mapped[str] = mapped_column(String(100))
    other_names: Mapped[str | None] = mapped_column(String(100))
    normalized_name: Mapped[str] = mapped_column(String(310), index=True)
    phone_raw: Mapped[str] = mapped_column(String(50))
    phone_normalized: Mapped[str] = mapped_column(String(30), index=True)
    email: Mapped[str | None] = mapped_column(String(254), index=True)
    region_code: Mapped[str | None] = mapped_column(String(60))
    district_code: Mapped[str | None] = mapped_column(String(60))
    community: Mapped[str] = mapped_column(String(150))
    directions: Mapped[str | None] = mapped_column(Text)
    location_status: Mapped[str | None] = mapped_column(String(60))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    sex: Mapped[str | None] = mapped_column(String(60))
    nationality: Mapped[str | None] = mapped_column(String(60))
    government_id_type: Mapped[str | None] = mapped_column(String(40))
    government_id_ciphertext: Mapped[str | None] = mapped_column(Text)
    government_id_hash: Mapped[str | None] = mapped_column(String(64), index=True)


class SensitiveProfile(Record, Base):
    __tablename__ = "participant_sensitive_profiles"
    __table_args__ = (
        CheckConstraint("current_income_amount IS NULL OR current_income_amount >= 0"),
    )
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("participants.id"), unique=True)
    refugee_status: Mapped[str | None] = mapped_column(String(60))
    displacement_status: Mapped[str | None] = mapped_column(String(60))
    displacement_reason: Mapped[str | None] = mapped_column(Text)
    original_community: Mapped[str | None] = mapped_column(String(150))
    host_community: Mapped[str | None] = mapped_column(String(150))
    disability_status: Mapped[str | None] = mapped_column(String(60))
    disability_specify: Mapped[str | None] = mapped_column(Text)
    current_income_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    income_frequency: Mapped[str | None] = mapped_column(String(20))


class Participant(Record, Base):
    __tablename__ = "participants"
    __table_args__ = (
        CheckConstraint(
            "onboarding_status IN ('NOT_STARTED','IN_PROGRESS','COMPLETE','BLOCKED','WITHDRAWN')"
        ),
        CheckConstraint(
            "readiness_status IN ('NOT_ASSESSED','DEVELOPING','JOB_READY','NOT_JOB_READY')"
        ),
        CheckConstraint(
            "availability_status IN ('UNKNOWN','AVAILABLE','TEMPORARILY_UNAVAILABLE','UNAVAILABLE')"
        ),
        CheckConstraint(
            "cv_status IN ('MISSING','UPLOADED','PARSING','REVIEW_REQUIRED','READY','NOT_REQUIRED')"
        ),
        Index("ix_participant_created_completed", "created_at", "completed_at"),
    )
    participant_code: Mapped[str] = mapped_column(String(40), unique=True)
    person_id: Mapped[UUID] = mapped_column(ForeignKey("people.id"), unique=True)
    programme_code: Mapped[str] = mapped_column(String(40), default="HAPPY")
    onboarding_status: Mapped[str] = mapped_column(String(30), default="NOT_STARTED", index=True)
    readiness_status: Mapped[str] = mapped_column(String(30), default="NOT_ASSESSED", index=True)
    availability_status: Mapped[str] = mapped_column(String(30), default="UNKNOWN")
    cv_status: Mapped[str] = mapped_column(String(30), default="MISSING")
    assigned_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    owner_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_type: Mapped[str | None] = mapped_column(String(60))
    source_detail: Mapped[str | None] = mapped_column(String(200))
    implementing_partner: Mapped[str | None] = mapped_column(String(150))
    employment_status: Mapped[str | None] = mapped_column(String(60))
    current_occupation: Mapped[str | None] = mapped_column(String(150))
    sector_code: Mapped[str | None] = mapped_column(String(60))
    industry_code: Mapped[str | None] = mapped_column(String(60))
    job_type: Mapped[str | None] = mapped_column(String(60))
    job_role: Mapped[str | None] = mapped_column(String(150))
    work_region_code: Mapped[str | None] = mapped_column(String(60))
    work_district_code: Mapped[str | None] = mapped_column(String(60))
    work_community: Mapped[str | None] = mapped_column(String(150))
    priority: Mapped[str] = mapped_column(String(15), default="NORMAL")
    next_action: Mapped[str | None] = mapped_column(String(500))
    next_action_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_sections: Mapped[list[str]] = mapped_column(JSON, default=list)
    training_summary: Mapped[str | None] = mapped_column(Text)
    training_interests: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    completion_mode: Mapped[str | None] = mapped_column(String(30))
    assisted_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_cv_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", use_alter=True, name="fk_participant_current_cv")
    )


class Consent(Record, Base):
    __tablename__ = "consents"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','WITHDRAWN')"),
        CheckConstraint("status != 'WITHDRAWN' OR withdrawn_at IS NOT NULL"),
    )
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("participants.id"), index=True)
    consent_type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    method: Mapped[str] = mapped_column(String(40))
    privacy_notice_version: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str | None] = mapped_column(Text)


class Education(Record, Base):
    __tablename__ = "participant_education"
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("participants.id"), index=True)
    education_level: Mapped[str] = mapped_column(String(100))
    institution: Mapped[str | None] = mapped_column(String(200))
    field_of_study: Mapped[str | None] = mapped_column(String(200))
    start_year: Mapped[int | None] = mapped_column(Integer)
    end_year: Mapped[int | None] = mapped_column(Integer)
    is_highest: Mapped[bool] = mapped_column(Boolean, default=False)


class Experience(Record, Base):
    __tablename__ = "participant_experience"
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("participants.id"), index=True)
    employer_name: Mapped[str] = mapped_column(String(200))
    role_title: Mapped[str] = mapped_column(String(200))
    sector: Mapped[str | None] = mapped_column(String(60))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)


class Skill(Record, Base):
    __tablename__ = "participant_skills"
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("participants.id"), index=True)
    skill_name: Mapped[str] = mapped_column(String(150))
    skill_code: Mapped[str | None] = mapped_column(String(60))
    level: Mapped[str | None] = mapped_column(String(60))
    source: Mapped[str | None] = mapped_column(String(100))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Document(Record, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("participant_id", "version_number", name="uq_cv_version"),
        CheckConstraint(
            "scan_status IN ('UPLOAD_PENDING','SCANNING','AVAILABLE','REJECTED','ARCHIVED')"
        ),
        CheckConstraint("size_bytes > 0"),
    )
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("participants.id"), index=True)
    document_code: Mapped[str] = mapped_column(String(40), unique=True)
    document_type: Mapped[str] = mapped_column(String(40), default="CV")
    storage_key: Mapped[str] = mapped_column(String(250), unique=True)
    original_filename: Mapped[str] = mapped_column(String(200))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    version_number: Mapped[int] = mapped_column(Integer)
    scan_status: Mapped[str] = mapped_column(String(30), default="SCANNING")
    scan_details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
