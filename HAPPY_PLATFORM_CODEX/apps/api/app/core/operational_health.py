"""Durable operational state and bounded, non-PII aggregate measurements."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.operational import OperationalState
from app.db.session import get_session_factory

Component = Literal["WORKER", "BACKUP", "RESTORE"]
logger = logging.getLogger("happy.operations")


def record_state(
    db: Session,
    component: Component,
    *,
    succeeded: bool | None = None,
    heartbeat: bool = False,
    current: datetime | None = None,
) -> None:
    timestamp = current or datetime.now(UTC)
    values: dict[str, Any] = {"component": component}
    updates: dict[str, Any] = {}
    if heartbeat:
        values["heartbeat_at"] = updates["heartbeat_at"] = timestamp
    if succeeded is not None:
        values["last_attempt_at"] = updates["last_attempt_at"] = timestamp
        key = "last_success_at" if succeeded else "last_failure_at"
        values[key] = updates[key] = timestamp
        values["consecutive_failures"] = 0 if succeeded else 1
        updates["consecutive_failures"] = (
            0 if succeeded else OperationalState.consecutive_failures + 1
        )
    if updates:
        db.execute(
            insert(OperationalState)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[OperationalState.component],
                set_=updates,
            )
        )


def persist_state(
    component: Component,
    *,
    succeeded: bool | None = None,
    heartbeat: bool = False,
) -> None:
    # Telemetry failure must neither fabricate operation success nor roll back a
    # successfully completed business operation. Missing/stale state is observable.
    try:
        with get_session_factory()() as db:
            record_state(db, component, succeeded=succeeded, heartbeat=heartbeat)
            db.commit()
    except Exception:
        logger.error("operational_checkpoint_unavailable")


def epoch(value: datetime | None) -> float:
    return value.timestamp() if value else 0.0


def snapshot(db: Session) -> dict[str, Any]:
    from app.integrations.intake.models import IntakeDocument, PublicIntake
    from app.modules.cv_parser.models import ParserJob
    from app.modules.demand.models import JobDescriptionVersion, PartnershipDocument
    from app.modules.iam.models import AuditEvent
    from app.modules.reporting.models import ReportExportJob
    from app.modules.supply.models import Document

    current = datetime.now(UTC)
    states = {row.component: row for row in db.scalars(select(OperationalState))}
    components = {
        component: {
            "heartbeat_timestamp": epoch(row.heartbeat_at) if row else 0.0,
            "last_attempt_timestamp": epoch(row.last_attempt_at) if row else 0.0,
            "last_success_timestamp": epoch(row.last_success_at) if row else 0.0,
            "last_failure_timestamp": epoch(row.last_failure_at) if row else 0.0,
            "consecutive_failures": row.consecutive_failures if row else 0,
        }
        for component in ("WORKER", "BACKUP", "RESTORE")
        for row in [states.get(component)]
    }
    queues: dict[str, Any] = {}
    for kind, model, queued in (
        ("REPORT", ReportExportJob, "PENDING"),
        ("PARSER", ParserJob, "QUEUED"),
    ):
        active = model.archived_at.is_(None)
        counts = dict(
            db.execute(
                select(model.status, func.count()).where(active).group_by(model.status)
            ).all()
        )
        oldest = db.scalar(select(func.min(model.created_at)).where(active, model.status == queued))
        stale = (
            db.scalar(
                select(func.count())
                .select_from(model)
                .where(
                    active,
                    model.status == "RUNNING",
                    model.lease_expires_at < current,
                )
            )
            or 0
        )
        last_success = db.scalar(
            select(func.max(model.completed_at)).where(active, model.status == "SUCCEEDED")
        )
        queues[kind] = {
            "queued": counts.get(queued, 0),
            "running": counts.get("RUNNING", 0),
            "failed": counts.get("FAILED", 0),
            "succeeded": counts.get("SUCCEEDED", 0),
            "oldest_queued_age_seconds": max(0.0, (current - oldest).total_seconds())
            if oldest
            else 0.0,
            "stale_leases": stale,
            "last_success_timestamp": epoch(last_success),
        }
    pending = 0
    rejected = 0
    for document in (Document, PartnershipDocument, JobDescriptionVersion):
        for status, target in (("SCANNING", "pending"), ("REJECTED", "rejected")):
            count = (
                db.scalar(
                    select(func.count())
                    .select_from(document)
                    .where(
                        document.scan_status == status,
                        document.archived_at.is_(None),
                    )
                )
                or 0
            )
            if target == "pending":
                pending += count
            else:
                rejected += count
    staged = (
        db.scalar(
            select(func.count())
            .select_from(IntakeDocument)
            .where(
                IntakeDocument.scan_status == "SCANNING",
                IntakeDocument.linked_document_id.is_(None),
            )
        )
        or 0
    )
    reviews = (
        db.scalar(
            select(func.count())
            .select_from(PublicIntake)
            .where(
                PublicIntake.status == "NEEDS_REVIEW",
            )
        )
        or 0
    )
    auth_failures = (
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.event_code == "auth.login_failed",
                AuditEvent.occurred_at >= current - timedelta(minutes=15),
            )
        )
        or 0
    )
    intake_counts = dict(
        db.execute(select(PublicIntake.status, func.count()).group_by(PublicIntake.status)).all()
    )
    return {
        "intake_submissions": intake_counts,
        "auth_failures_15m": auth_failures,
        "components": components,
        "queues": queues,
        "scan_backlog": pending + staged,
        "rejected_documents": rejected,
        "duplicate_reviews": reviews,
    }
