from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
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


class ReportTarget(Record, Base):
    __tablename__ = "report_targets"
    __table_args__ = (
        UniqueConstraint(
            "kpi_code",
            "period_start",
            "period_end",
            "dimension_key",
            name="uq_report_target_period_dimension",
        ),
        CheckConstraint("period_end >= period_start", name="ck_report_target_period"),
        CheckConstraint("target_value >= 0", name="ck_report_target_value"),
        CheckConstraint(
            "forecast_value IS NULL OR forecast_value >= 0",
            name="ck_report_target_forecast",
        ),
        Index("ix_report_target_period", "period_start", "period_end"),
    )
    kpi_code: Mapped[str] = mapped_column(String(40), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    dimension_key: Mapped[str] = mapped_column(String(100), default="GLOBAL")
    target_value: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    forecast_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    notes: Mapped[str | None] = mapped_column(Text)


class ReportExportJob(Record, Base):
    __tablename__ = "report_export_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCEEDED','FAILED')",
            name="ck_report_export_job_status",
        ),
        CheckConstraint("row_count IS NULL OR row_count >= 0", name="ck_report_export_row_count"),
        CheckConstraint("attempt_count >= 0", name="ck_report_export_job_attempts"),
        Index("ix_report_export_requester_created", "requested_by", "created_at"),
    )
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    kpi_code: Mapped[str] = mapped_column(String(40))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    format: Mapped[str] = mapped_column(String(10), default="CSV")
    include_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    storage_key: Mapped[str | None] = mapped_column(String(300), unique=True)
    row_count: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(500))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
