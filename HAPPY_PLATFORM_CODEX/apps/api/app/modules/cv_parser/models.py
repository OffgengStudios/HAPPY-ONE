from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.provenance import Provenance
from app.modules.demand.models import Record
from app.modules.iam.models import now


class ParserJob(Record, Base):
    __tablename__ = "cv_parser_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_cv_parser_job_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_cv_parser_job_attempts"),
        Index(
            "uq_cv_parser_active_document",
            "document_id",
            unique=True,
            postgresql_where=text("status IN ('QUEUED','RUNNING') AND archived_at IS NULL"),
        ),
    )
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    document_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", index=True)
    provider: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    input_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(String(500))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    lease_owner: Mapped[str | None] = mapped_column(String(100))


class ParserResult(Provenance, Base):
    __tablename__ = "cv_parser_results"
    __table_args__ = (
        CheckConstraint(
            "review_status IN ('PENDING_REVIEW','PARTIALLY_REVIEWED','APPROVED','REJECTED')",
            name="ck_cv_parser_result_review_status",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("cv_parser_jobs.id"), unique=True)
    schema_version: Mapped[str] = mapped_column(String(30), default="1")
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    suggestions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    review_status: Mapped[str] = mapped_column(String(30), default="PENDING_REVIEW")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ParserReview(Provenance, Base):
    __tablename__ = "cv_parser_reviews"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('APPROVE','REJECT','EDIT')", name="ck_cv_parser_review_decision"
        ),
        UniqueConstraint("result_id", "field", name="uq_cv_parser_review_field"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    result_id: Mapped[UUID] = mapped_column(ForeignKey("cv_parser_results.id"), index=True)
    field: Mapped[str] = mapped_column(String(100))
    decision: Mapped[str] = mapped_column(String(20))
    original_value_json: Mapped[Any] = mapped_column(JSON)
    approved_value_json: Mapped[Any | None] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float)
    reviewed_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
