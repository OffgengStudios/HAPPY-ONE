from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.modules.demand.models import Record


class Task(Record, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN','IN_PROGRESS','BLOCKED','COMPLETED','CANCELLED')",
            name="ck_task_status",
        ),
        CheckConstraint("priority IN ('LOW','NORMAL','HIGH','URGENT')", name="ck_task_priority"),
        Index("ix_task_owner_status_due", "owner_user_id", "status", "due_at"),
        Index("ix_task_team_status_due", "owner_team", "status", "due_at"),
    )

    task_code: Mapped[str] = mapped_column(String(40), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    priority: Mapped[str] = mapped_column(String(10), default="NORMAL")
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    owner_team: Mapped[str | None] = mapped_column(String(40), index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[UUID | None] = mapped_column(index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Handoff(Record, Base):
    __tablename__ = "handoffs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('SENT','ACCEPTED','IN_PROGRESS','COMPLETED','RETURNED','CANCELLED')",
            name="ck_handoff_status",
        ),
        Index("ix_handoff_to_status_sent", "to_workstream", "status", "sent_at"),
        Index("ix_handoff_assignee_status", "assigned_to", "status"),
    )

    from_workstream: Mapped[str] = mapped_column(String(40))
    to_workstream: Mapped[str] = mapped_column(String(40))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[UUID] = mapped_column(index=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="SENT")
    sent_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    assigned_to: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    return_reason: Mapped[str | None] = mapped_column(Text)


class Notification(Record, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('TASK_ASSIGNED','HANDOFF_SENT','HANDOFF_ACCEPTED','SYSTEM')",
            name="ck_notification_kind",
        ),
        Index("ix_notification_recipient_read", "recipient_user_id", "read_at", "created_at"),
    )

    recipient_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[UUID | None] = mapped_column(index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
