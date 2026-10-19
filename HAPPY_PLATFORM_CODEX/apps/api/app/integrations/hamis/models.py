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


class HamisInboundEvent(Base):
    __tablename__ = "hamis_inbound_events"
    __table_args__ = (
        UniqueConstraint("external_event_id", name="uq_hamis_inbound_event"),
        CheckConstraint(
            "event_type IN ('PARTICIPANT_UPSERT','CONSENT_RECORDED',"
            "'TRAINING_RECORDED','PLACEMENT_RECORDED')",
            name="ck_hamis_event_type",
        ),
        CheckConstraint(
            "status IN ('RECEIVED','PROCESSING','APPLIED','NEEDS_REVIEW','REJECTED','FAILED')",
            name="ck_hamis_event_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_hamis_event_attempts"),
        Index("ix_hamis_event_status_received", "status", "received_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    external_event_id: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(40))
    payload_hash: Mapped[str] = mapped_column(String(64))
    payload_ciphertext: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="RECEIVED")
    review_reason: Mapped[str | None] = mapped_column(Text)
    participant_id: Mapped[UUID | None] = mapped_column(ForeignKey("participants.id"), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, default=1)
