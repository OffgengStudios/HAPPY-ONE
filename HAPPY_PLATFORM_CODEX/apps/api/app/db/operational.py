"""Small durable operational checkpoints, never programme or participant data."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OperationalState(Base):
    __tablename__ = "operational_state"
    __table_args__ = (
        CheckConstraint(
            "component IN ('WORKER','BACKUP','RESTORE')", name="ck_operational_component"
        ),
        CheckConstraint("consecutive_failures >= 0", name="ck_operational_failures"),
    )
    component: Mapped[str] = mapped_column(String(20), primary_key=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
