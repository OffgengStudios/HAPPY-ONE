from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.modules.iam.models import now


class PublicIntake(Base):
    """Submission receipt/review evidence, never a second participant master."""

    __tablename__ = "public_intakes"
    __table_args__ = (
        UniqueConstraint("source", "submission_id", name="uq_public_intake_submission"),
        CheckConstraint(
            "source IN ('HAMIS','EMPLOYER_INTAKE','UNIJAY_FASHION')", name="ck_public_intake_source"
        ),
        CheckConstraint(
            "status IN ('RECEIVED','NEEDS_REVIEW','APPLIED','REJECTED')",
            name="ck_public_intake_status",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(30))
    submission_id: Mapped[UUID] = mapped_column()
    payload_hash: Mapped[str] = mapped_column(String(64))
    payload_ciphertext: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="RECEIVED", index=True)
    participant_id: Mapped[UUID | None] = mapped_column(ForeignKey("participants.id"))
    employer_submission_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("employer_portal_submissions.id")
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class IntakeDocument(Base):
    __tablename__ = "intake_documents"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('CV','MOU','AGREEMENT','JD','SUPPORTING')", name="ck_intake_document_kind"
        ),
        CheckConstraint(
            "scan_status IN ('SCANNING','AVAILABLE','REJECTED','ARCHIVED')",
            name="ck_intake_document_scan",
        ),
        CheckConstraint("size_bytes > 0", name="ck_intake_document_size"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    intake_id: Mapped[UUID] = mapped_column(ForeignKey("public_intakes.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    vacancy_index: Mapped[int | None] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(300), unique=True)
    original_filename: Mapped[str] = mapped_column(String(200))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    scan_status: Mapped[str] = mapped_column(String(20))
    linked_document_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
