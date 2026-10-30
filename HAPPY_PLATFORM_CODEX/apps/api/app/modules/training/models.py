from datetime import date
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.modules.demand.models import Record


class Training(Record, Base):
    __tablename__ = "trainings"
    __table_args__ = (
        CheckConstraint("mode IN ('IN_PERSON','VIRTUAL','HYBRID')", name="ck_training_mode"),
        CheckConstraint(
            "trainer_type IN ('INTERNAL','EXTERNAL_PARTNER')", name="ck_training_trainer_type"
        ),
        CheckConstraint(
            "status IN ('DRAFT','PLANNED','IN_PROGRESS','COMPLETED','CANCELLED')",
            name="ck_training_status",
        ),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_training_dates"),
        Index("ix_training_status_start", "status", "start_date"),
    )

    training_code: Mapped[str] = mapped_column(String(40), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    training_type: Mapped[str] = mapped_column(String(60))
    partner_organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    trainer_type: Mapped[str] = mapped_column(String(30))
    mode: Mapped[str] = mapped_column(String(20))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    location_region_code: Mapped[str | None] = mapped_column(String(60))
    location_district_code: Mapped[str | None] = mapped_column(String(60))
    location_community: Mapped[str | None] = mapped_column(String(150))
    location_text: Mapped[str | None] = mapped_column(Text)
    virtual_platform: Mapped[str | None] = mapped_column(String(120))
    modules_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    agriculture_sector: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True)


class TrainingAttendance(Record, Base):
    __tablename__ = "training_attendance"
    __table_args__ = (
        UniqueConstraint("training_id", "participant_id", name="uq_training_participant"),
        CheckConstraint(
            "attendance_status IN ('PRESENT','ABSENT','LATE','EXCUSED')",
            name="ck_training_attendance_status",
        ),
        CheckConstraint(
            "completion_status IN ('NOT_STARTED','IN_PROGRESS','COMPLETED','NOT_COMPLETED')",
            name="ck_training_completion_status",
        ),
    )

    training_id: Mapped[UUID] = mapped_column(ForeignKey("trainings.id"), index=True)
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("participants.id"), index=True)
    attendance_status: Mapped[str] = mapped_column(String(20), default="PRESENT")
    completion_status: Mapped[str] = mapped_column(String(20), default="NOT_STARTED")
    certificate_issued: Mapped[bool] = mapped_column(Boolean, default=False)
    certificate_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    received_modules: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    completed_modules: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
