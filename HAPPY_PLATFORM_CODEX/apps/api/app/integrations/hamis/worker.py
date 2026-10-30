import os
import socket
from datetime import timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_session_factory
from app.integrations.hamis import service
from app.integrations.hamis.models import HamisInboundEvent
from app.modules.iam.actors import AuditActor
from app.modules.iam.models import now
from app.modules.iam.service import audit

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def claim(db: Session) -> UUID | None:
    current = now()
    row = db.scalar(
        select(HamisInboundEvent)
        .where(
            HamisInboundEvent.status.in_(["RECEIVED", "PROCESSING"]),
            or_(
                HamisInboundEvent.next_attempt_at.is_(None),
                HamisInboundEvent.next_attempt_at <= current,
            ),
            or_(
                HamisInboundEvent.lease_expires_at.is_(None),
                HamisInboundEvent.lease_expires_at < current,
            ),
        )
        .order_by(HamisInboundEvent.received_at, HamisInboundEvent.id)
        .with_for_update(skip_locked=True)
    )
    if not row:
        return None
    if row.attempt_count >= settings.background_job_max_attempts:
        row.status = "FAILED"
        row.error_code = "RETRY_LIMIT_EXCEEDED"
        row.error_message = "The final worker lease expired. Review the failure before retrying."
        row.processed_at = current
        row.lease_owner = None
        row.lease_expires_at = None
        row.next_attempt_at = None
        row.version += 1
        audit(
            db,
            "hamis.event_failed",
            AuditActor("INTEGRATION", "HAMIS"),
            "hamis_inbound_event",
            row.id,
            result="FAILURE",
            changes={"error_code": row.error_code, "attempt_count": row.attempt_count},
        )
        db.commit()
        return row.id
    row.status = "PROCESSING"
    row.version += 1
    row.attempt_count += 1
    row.lease_owner = WORKER_ID
    row.lease_expires_at = current + timedelta(seconds=settings.background_job_lease_seconds)
    row.next_attempt_at = None
    db.commit()
    return row.id


def process(db: Session, identifier: UUID) -> None:
    row = db.get(HamisInboundEvent, identifier, with_for_update=True, populate_existing=True)
    if (
        not row
        or row.status != "PROCESSING"
        or row.lease_owner != WORKER_ID
        or not row.lease_expires_at
        or row.lease_expires_at <= now()
    ):
        return
    try:
        service.process_event(db, row)
        row.error_code = None
        row.error_message = None
        row.lease_owner = None
        row.lease_expires_at = None
        audit(
            db,
            "hamis.event_processed",
            AuditActor("INTEGRATION", "HAMIS"),
            "hamis_inbound_event",
            row.id,
            changes={"event_type": row.event_type, "status": row.status},
        )
        db.commit()
    except Exception:
        db.rollback()
        row = db.get(HamisInboundEvent, identifier, with_for_update=True, populate_existing=True)
        if not row or row.status != "PROCESSING" or row.lease_owner != WORKER_ID:
            return
        row.version += 1
        row.error_code = "HAMIS_PROCESSING_FAILED"
        row.error_message = "The HAMIS event could not be processed."
        row.lease_owner = None
        row.lease_expires_at = None
        if row.attempt_count < settings.background_job_max_attempts:
            row.status = "RECEIVED"
            row.next_attempt_at = now() + timedelta(seconds=min(900, 15 * 2**row.attempt_count))
        else:
            row.status = "FAILED"
            row.processed_at = now()
            audit(
                db,
                "hamis.event_failed",
                AuditActor("INTEGRATION", "HAMIS"),
                "hamis_inbound_event",
                row.id,
                result="FAILURE",
                changes={"error_code": row.error_code, "attempt_count": row.attempt_count},
            )
        db.commit()


def run_once() -> bool:
    with get_session_factory()() as db:
        identifier = claim(db)
        if identifier is None:
            return False
        process(db, identifier)
        return True
