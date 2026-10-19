from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.modules.iam.models import now


class EmployerSubmission(Base):
    __tablename__ = "employer_portal_submissions"
    __table_args__ = (
        UniqueConstraint("external_submission_id", name="uq_employer_portal_submission"),
        CheckConstraint(
            "status IN ('NEW','NEEDS_REVIEW','CONVERTED','REJECTED','ARCHIVED')",
            name="ck_employer_submission_status",
        ),
        Index("ix_employer_submission_status_received", "status", "received_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    external_submission_id: Mapped[str] = mapped_column(String(200))
    reference_number: Mapped[str | None] = mapped_column(String(80))
    payload_hash: Mapped[str] = mapped_column(String(64))
    payload_ciphertext: Mapped[str] = mapped_column(Text)
    company_name: Mapped[str] = mapped_column(String(200))
    vacancy_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="NEW")
    review_notes: Mapped[str | None] = mapped_column(Text)
    organization_id: Mapped[UUID | None] = mapped_column(ForeignKey("organizations.id"))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    converted_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
