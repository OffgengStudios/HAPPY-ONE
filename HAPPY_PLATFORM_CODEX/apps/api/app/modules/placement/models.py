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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.provenance import Provenance
from app.modules.demand.models import Record
from app.modules.iam.models import now
from app.modules.matching.models import ACTOR_CHECK, ACTOR_ID_CHECK


class Placement(Record, Base):
    __tablename__ = "placements"
    __table_args__ = (
        UniqueConstraint("candidate_vacancy_id", name="uq_placement_candidate"),
        CheckConstraint(
            "status IN ('START_PENDING','STARTED','AWAITING_FIRST_INCOME','CONFIRMED',"
            "'ENDED','FAILED_TO_START','CANCELLED')",
            name="ck_placement_status",
        ),
        CheckConstraint("salary_amount IS NULL OR salary_amount >= 0", name="ck_placement_salary"),
        CheckConstraint(
            "salary_frequency IS NULL OR salary_frequency IN "
            "('DAILY','WEEKLY','BIWEEKLY','MONTHLY')",
            name="ck_placement_salary_frequency",
        ),
        CheckConstraint(
            "payroll_frequency IS NULL OR payroll_frequency IN "
            "('DAILY','WEEKLY','BIWEEKLY','MONTHLY')",
            name="ck_placement_payroll_frequency",
        ),
        CheckConstraint(
            "status NOT IN ('STARTED','AWAITING_FIRST_INCOME','CONFIRMED','ENDED') "
            "OR actual_start_date IS NOT NULL",
            name="ck_placement_actual_start",
        ),
        CheckConstraint(
            "status <> 'CONFIRMED' OR confirmed_at IS NOT NULL",
            name="ck_placement_confirmation",
        ),
        CheckConstraint(
            "status <> 'ENDED' OR employment_end_date IS NOT NULL",
            name="ck_placement_end",
        ),
        Index("ix_placement_status_due", "status", "expected_first_income_date"),
        Index("ix_placement_confirmed_at", "confirmed_at"),
        Index("ix_placement_actual_start_date", "actual_start_date"),
    )
    placement_code: Mapped[str] = mapped_column(String(40), unique=True)
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("participants.id"), index=True)
    candidate_vacancy_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_vacancies.id"), index=True
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    vacancy_id: Mapped[UUID] = mapped_column(ForeignKey("vacancies.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="START_PENDING", index=True)
    expected_start_date: Mapped[date | None] = mapped_column(Date)
    actual_start_date: Mapped[date | None] = mapped_column(Date)
    salary_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    salary_currency: Mapped[str] = mapped_column(String(3), default="GHS")
    salary_frequency: Mapped[str | None] = mapped_column(String(20))
    payroll_frequency: Mapped[str | None] = mapped_column(String(20))
    payday_rule_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    expected_first_income_date: Mapped[date | None] = mapped_column(Date)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    employment_end_date: Mapped[date | None] = mapped_column(Date)
    employment_end_reason: Mapped[str | None] = mapped_column(String(60))
    currently_working: Mapped[bool | None] = mapped_column(Boolean)
    owner_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)


class FirstIncomeVerification(Record, Base):
    __tablename__ = "first_income_verifications"
    __table_args__ = (
        UniqueConstraint("placement_id", name="uq_first_income_placement"),
        CheckConstraint(
            "status IN ('NOT_SCHEDULED','UPCOMING','DUE','OVERDUE','CONFIRMED',"
            "'PAYMENT_DELAYED','CANDIDATE_LEFT','EXCEPTION')",
            name="ck_first_income_status",
        ),
        CheckConstraint(
            "status <> 'CONFIRMED' OR (actual_income_received_date IS NOT NULL "
            "AND verified_at IS NOT NULL AND verified_by IS NOT NULL)",
            name="ck_first_income_confirmation",
        ),
        CheckConstraint(
            "amount_received IS NULL OR amount_received >= 0", name="ck_first_income_amount"
        ),
        Index("ix_first_income_status_due", "status", "verification_due_date"),
    )
    placement_id: Mapped[UUID] = mapped_column(ForeignKey("placements.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="NOT_SCHEDULED", index=True)
    verification_due_date: Mapped[date | None] = mapped_column(Date)
    actual_income_received_date: Mapped[date | None] = mapped_column(Date)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    amount_received: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    evidence_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"))
    exception_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class PlacementHistory(Base):
    __tablename__ = "placement_history"
    __table_args__ = (
        CheckConstraint(ACTOR_CHECK, name="ck_placement_history_actor"),
        CheckConstraint(ACTOR_ID_CHECK, name="ck_placement_history_actor_id"),
        Index("ix_placement_history_chronology", "placement_id", "occurred_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    placement_id: Mapped[UUID] = mapped_column(ForeignKey("placements.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text)
    actor_type: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[str | None] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EmploymentStatusHistory(Provenance, Base):
    __tablename__ = "employment_status_history"
    __table_args__ = (
        CheckConstraint(
            "status IN ('WORKING','ENDED','FAILED_TO_START','CANCELLED')",
            name="ck_employment_history_status",
        ),
        Index("ix_employment_history_chronology", "placement_id", "effective_date", "id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    placement_id: Mapped[UUID] = mapped_column(ForeignKey("placements.id"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    effective_date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(30), default="STAFF")
    verified_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
