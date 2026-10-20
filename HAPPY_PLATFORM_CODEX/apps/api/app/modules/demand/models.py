from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

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
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.provenance import Provenance
from app.modules.iam.models import now


class Record(Provenance):
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)


class Organization(Record, Base):
    __tablename__ = "organizations"
    organization_code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(String(200), index=True)
    organization_type: Mapped[str] = mapped_column(String(60))
    industry_code: Mapped[str | None] = mapped_column(String(60))
    sector_code: Mapped[str | None] = mapped_column(String(60))
    region_code: Mapped[str | None] = mapped_column(String(60))
    district_code: Mapped[str | None] = mapped_column(String(60))
    community: Mapped[str | None] = mapped_column(String(150))
    address_text: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(500))
    relationship_owner_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))


class Contact(Record, Base):
    __tablename__ = "organization_contacts"
    __table_args__ = (
        Index(
            "uq_active_primary_contact",
            "organization_id",
            unique=True,
            postgresql_where=text("is_primary AND is_active AND archived_at IS NULL"),
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    job_title: Mapped[str | None] = mapped_column(String(150))
    phone_raw: Mapped[str | None] = mapped_column(String(50))
    phone_normalized: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(254))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)


class Partnership(Record, Base):
    __tablename__ = "partnerships"
    __table_args__ = (
        CheckConstraint(
            "status IN ('LEAD','CONTACTED','ENGAGED','INTERESTED',"
            "'MOU_PENDING','MOU_SIGNED','ACTIVE','INACTIVE','DECLINED')"
        ),
        CheckConstraint(
            "NOT mou_required OR status NOT IN ('MOU_SIGNED','ACTIVE') OR mou_signed_at IS NOT NULL"
        ),
        CheckConstraint(
            "status != 'MOU_SIGNED' OR mou_signed_at IS NOT NULL", name="ck_partnership_signed_date"
        ),
        CheckConstraint(
            "partnership_type IN ('TRAINING','RECRUITMENT','COMBINED')",
            name="ck_partnership_type",
        ),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_partnership_dates"),
    )
    partnership_code: Mapped[str] = mapped_column(
        String(40), unique=True, default=lambda: "PAR-" + uuid4().hex[:12].upper()
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    partnership_type: Mapped[str] = mapped_column(String(20), default="RECRUITMENT")
    start_date: Mapped[date] = mapped_column(Date, default=date.today)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="LEAD")
    mou_required: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[str] = mapped_column(String(15), default="NORMAL")
    owner_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mou_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mou_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    next_action: Mapped[str | None] = mapped_column(String(500))
    next_action_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PartnershipDocument(Record, Base):
    __tablename__ = "partnership_documents"
    __table_args__ = (
        UniqueConstraint(
            "partnership_id", "version_number", name="uq_partnership_document_version"
        ),
        CheckConstraint(
            "scan_status IN ('SCANNING','AVAILABLE','REJECTED','ARCHIVED')",
            name="ck_partnership_document_scan_status",
        ),
        CheckConstraint("size_bytes > 0", name="ck_partnership_document_size"),
    )
    partnership_id: Mapped[UUID] = mapped_column(ForeignKey("partnerships.id"), index=True)
    document_code: Mapped[str] = mapped_column(String(40), unique=True)
    storage_key: Mapped[str] = mapped_column(String(300), unique=True)
    original_filename: Mapped[str] = mapped_column(String(200))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    version_number: Mapped[int] = mapped_column(Integer)
    scan_status: Mapped[str] = mapped_column(String(30), default="SCANNING")
    scan_details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Vacancy(Record, Base):
    __tablename__ = "vacancies"
    __table_args__ = (
        CheckConstraint("required_headcount > 0"),
        CheckConstraint("salary_min IS NULL OR salary_min >= 0"),
        CheckConstraint("salary_max IS NULL OR salary_max >= 0"),
        CheckConstraint("salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max"),
        CheckConstraint(
            "status IN ('DRAFT','PENDING_CONFIRMATION','ACTIVE','PARTIALLY_FILLED',"
            "'ON_HOLD','FULLY_FILLED','CLOSED','CANCELLED')"
        ),
        CheckConstraint(
            "status NOT IN ('CLOSED','CANCELLED') OR "
            "(closure_reason IS NOT NULL AND closed_at IS NOT NULL)"
        ),
    )
    vacancy_code: Mapped[str] = mapped_column(String(40), unique=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)
    priority: Mapped[str] = mapped_column(String(15), default="NORMAL")
    description: Mapped[str | None] = mapped_column(Text)
    location_region_code: Mapped[str | None] = mapped_column(String(60))
    location_district_code: Mapped[str | None] = mapped_column(String(60))
    location_community: Mapped[str | None] = mapped_column(String(150))
    location_directions: Mapped[str | None] = mapped_column(Text)
    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    salary_currency: Mapped[str] = mapped_column(String(3), default="GHS")
    salary_frequency: Mapped[str | None] = mapped_column(String(20))
    work_days_text: Mapped[str | None] = mapped_column(String(150))
    work_hours_text: Mapped[str | None] = mapped_column(String(150))
    accommodation_available: Mapped[bool | None] = mapped_column(Boolean)
    deadline: Mapped[date | None] = mapped_column(Date)
    benefits: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    required_headcount: Mapped[int] = mapped_column(Integer)
    owner_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    demand_owner_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closure_reason: Mapped[str | None] = mapped_column(String(100))
    closure_note: Mapped[str | None] = mapped_column(Text)


class JobDescriptionVersion(Record, Base):
    __tablename__ = "job_description_versions"
    __table_args__ = (
        UniqueConstraint("vacancy_id", "version_number", name="uq_job_description_version"),
        CheckConstraint(
            "scan_status IN ('SCANNING','AVAILABLE','REJECTED','ARCHIVED')",
            name="ck_job_description_scan_status",
        ),
        CheckConstraint("size_bytes > 0", name="ck_job_description_size"),
    )
    vacancy_id: Mapped[UUID] = mapped_column(ForeignKey("vacancies.id"), index=True)
    document_code: Mapped[str] = mapped_column(String(40), unique=True)
    storage_key: Mapped[str] = mapped_column(String(300), unique=True)
    original_filename: Mapped[str] = mapped_column(String(200))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    version_number: Mapped[int] = mapped_column(Integer)
    scan_status: Mapped[str] = mapped_column(String(30), default="SCANNING")
    scan_details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Requirement(Record, Base):
    __tablename__ = "vacancy_requirements"
    __table_args__ = (CheckConstraint("weight >= 0"),)
    vacancy_id: Mapped[UUID] = mapped_column(ForeignKey("vacancies.id"), index=True)
    criterion_type: Mapped[str] = mapped_column(String(60))
    criterion_key: Mapped[str] = mapped_column(String(100))
    operator: Mapped[str] = mapped_column(String(10))
    value_json: Mapped[Any] = mapped_column(JSON)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=1)
    display_order: Mapped[int] = mapped_column(Integer, default=0)


class VacancyChange(Base):
    __tablename__ = "vacancy_changes"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    vacancy_id: Mapped[UUID] = mapped_column(ForeignKey("vacancies.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(100))
    old_value_json: Mapped[Any | None] = mapped_column(JSON)
    new_value_json: Mapped[Any | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReferenceData(Base):
    __tablename__ = "demand_reference_data"
    group_code: Mapped[str] = mapped_column(String(40), primary_key=True)
    code: Mapped[str] = mapped_column(String(60), primary_key=True)
    label: Mapped[str] = mapped_column(String(100))
