from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.modules.iam.models import now


class ExternalReference(Base):
    __tablename__ = "external_references"
    __table_args__ = (
        UniqueConstraint(
            "external_system", "entity_type", "external_id", name="uq_external_reference_key"
        ),
        Index("ix_external_reference_entity", "entity_type", "entity_id"),
        CheckConstraint(
            "entity_type IN ('PARTICIPANT','ORGANIZATION','VACANCY')",
            name="ck_external_reference_entity_type",
        ),
        CheckConstraint(
            "external_system ~ '^[A-Z][A-Z0-9_]{0,59}$'", name="ck_external_reference_system"
        ),
        CheckConstraint("length(trim(external_id)) > 0", name="ck_external_reference_identifier"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[UUID] = mapped_column(Uuid)
    external_system: Mapped[str] = mapped_column(String(60))
    external_id: Mapped[str] = mapped_column(String(200))
    external_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    version: Mapped[int] = mapped_column(Integer, default=1)
