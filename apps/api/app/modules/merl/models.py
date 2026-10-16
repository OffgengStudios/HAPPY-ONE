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
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.provenance import Provenance
from app.modules.demand.models import Record
from app.modules.iam.models import now


class FollowUpTemplate(Record, Base):
    __tablename__ = "follow_up_templates"
    __table_args__ = (
        CheckConstraint(
            "anchor IN ('ACTUAL_START','CONFIRMED')", name="ck_follow_up_template_anchor"
        ),
        CheckConstraint("offset_days >= 0", name="ck_follow_up_template_offset"),
    )
    template_code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    follow_up_type: Mapped[str] = mapped_column(String(60))
    anchor: Mapped[str] = mapped_column(String(30))
    offset_days: Mapped[int] = mapped_column(Integer)
    required_questions: Mapped[list[str]] = mapped_column(JSON, default=list)
    owner_role_code: Mapped[str | None] = mapped_column(String(40))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class FollowUp(Record, Base):
    __tablename__ = "follow_ups"
    __table_args__ = (
        CheckConstraint(
            "status IN ('SCHEDULED','DUE','OVERDUE','COMPLETED','CANCELLED')",
            name="ck_follow_up_status",
        ),
        CheckConstraint(
            "contact_result IS NULL OR contact_result IN "
            "('REACHED','NOT_REACHED','DECLINED','RESCHEDULED')",
            name="ck_follow_up_contact_result",
        ),
        CheckConstraint(
            "status <> 'COMPLETED' OR (completed_at IS NOT NULL AND completed_by IS NOT NULL "
            "AND contact_result IS NOT NULL)",
            name="ck_follow_up_completion",
        ),
        Index("ix_follow_up_status_schedule", "status", "scheduled_for"),
    )
    follow_up_code: Mapped[str] = mapped_column(String(40), unique=True)
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("participants.id"), index=True)
    placement_id: Mapped[UUID] = mapped_column(ForeignKey("placements.id"), index=True)
    template_id: Mapped[UUID | None] = mapped_column(ForeignKey("follow_up_templates.id"))
    follow_up_type: Mapped[str] = mapped_column(String(60))
    scheduled_for: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(20), default="SCHEDULED", index=True)
    owner_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    contact_result: Mapped[str | None] = mapped_column(String(30))
    notes: Mapped[str | None] = mapped_column(Text)


class Outcome(Record, Base):
    __tablename__ = "outcomes"
    __table_args__ = (
        UniqueConstraint("follow_up_id", name="uq_outcome_follow_up"),
        CheckConstraint(
            "current_income_amount IS NULL OR current_income_amount >= 0",
            name="ck_outcome_income",
        ),
        CheckConstraint(
            "income_frequency IS NULL OR income_frequency IN "
            "('DAILY','WEEKLY','BIWEEKLY','MONTHLY','OTHER')",
            name="ck_outcome_income_frequency",
        ),
        CheckConstraint(
            "job_satisfaction IS NULL OR job_satisfaction BETWEEN 1 AND 5",
            name="ck_outcome_satisfaction",
        ),
        Index("ix_outcome_placement_as_of", "placement_id", "as_of_date"),
    )
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("participants.id"), index=True)
    placement_id: Mapped[UUID] = mapped_column(ForeignKey("placements.id"), index=True)
    follow_up_id: Mapped[UUID | None] = mapped_column(ForeignKey("follow_ups.id"))
    as_of_date: Mapped[date] = mapped_column(Date, index=True)
    currently_working: Mapped[bool] = mapped_column(Boolean)
    current_employer: Mapped[str | None] = mapped_column(String(200))
    current_role: Mapped[str | None] = mapped_column(String(200))
    current_income_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    income_frequency: Mapped[str | None] = mapped_column(String(20))
    job_satisfaction: Mapped[int | None] = mapped_column(Integer)
    challenges_text: Mapped[str | None] = mapped_column(Text)
    progress_text: Mapped[str | None] = mapped_column(Text)
    skills_gained_text: Mapped[str | None] = mapped_column(Text)
    household_community_effects_text: Mapped[str | None] = mapped_column(Text)
    support_needed_text: Mapped[str | None] = mapped_column(Text)
    impact_story_potential: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    verified_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))


class OutcomeRevision(Provenance, Base):
    __tablename__ = "outcome_revisions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    outcome_id: Mapped[UUID] = mapped_column(ForeignKey("outcomes.id"), index=True)
    previous_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text)
    corrected_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DataQualityIssue(Record, Base):
    __tablename__ = "data_quality_issues"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('PARTICIPANT','PLACEMENT','FOLLOW_UP','OUTCOME')",
            name="ck_data_quality_entity_type",
        ),
        CheckConstraint(
            "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_data_quality_severity",
        ),
        CheckConstraint(
            "status IN ('OPEN','IN_PROGRESS','RESOLVED','DISMISSED')",
            name="ck_data_quality_status",
        ),
        CheckConstraint(
            "status NOT IN ('RESOLVED','DISMISSED') OR resolved_at IS NOT NULL",
            name="ck_data_quality_resolution",
        ),
        Index("ix_data_quality_status_severity", "status", "severity"),
    )
    issue_code: Mapped[str] = mapped_column(String(40), unique=True)
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    issue_type: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    description: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
