import os
import socket
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_session_factory
from app.modules.iam.actors import AuditActor
from app.modules.iam.service import audit
from app.modules.reporting import schemas as data
from app.modules.reporting import service
from app.modules.reporting.models import ReportExportJob
from app.storage.s3 import get_storage_client

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def _now() -> datetime:
    return datetime.now(UTC)


def claim(db: Session) -> UUID | None:
    current = _now()
    row = db.scalar(
        select(ReportExportJob)
        .where(
            ReportExportJob.status.in_(["PENDING", "RUNNING"]),
            or_(
                ReportExportJob.next_attempt_at.is_(None),
                ReportExportJob.next_attempt_at <= current,
            ),
            or_(
                ReportExportJob.lease_expires_at.is_(None),
                ReportExportJob.lease_expires_at < current,
            ),
            ReportExportJob.attempt_count < settings.background_job_max_attempts,
            ReportExportJob.archived_at.is_(None),
        )
        .order_by(ReportExportJob.created_at, ReportExportJob.id)
        .with_for_update(skip_locked=True)
    )
    if not row:
        return None
    row.status = "RUNNING"
    row.attempt_count += 1
    row.started_at = row.started_at or current
    row.lease_owner = WORKER_ID
    row.lease_expires_at = current + timedelta(seconds=settings.background_job_lease_seconds)
    row.next_attempt_at = None
    db.commit()
    return row.id


def process(db: Session, identifier: UUID) -> None:
    row = db.get(ReportExportJob, identifier)
    if not row or row.status != "RUNNING" or row.lease_owner != WORKER_ID:
        return
    try:
        values = data.Period(date_from=row.period_start, date_to=row.period_end)
        rows = service.drilldown(db, row.kpi_code, values, limit=None)
        content = service.csv_export(row.kpi_code, rows).encode("utf-8")
        key = f"reports/exports/{row.requested_by}/{row.id}.csv"
        get_storage_client().put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=content,
            ContentType="text/csv; charset=utf-8",
        )
        row.storage_key = key
        row.row_count = len(rows)
        row.status = "SUCCEEDED"
        row.completed_at = _now()
        row.error_code = None
        row.error_message = None
        row.lease_owner = None
        row.lease_expires_at = None
        audit(
            db,
            "report.export_completed",
            AuditActor("SYSTEM"),
            "report_export_job",
            row.id,
            changes={"kpi_code": row.kpi_code, "row_count": len(rows)},
        )
        db.commit()
    except Exception:
        db.rollback()
        row = db.get(ReportExportJob, identifier)
        if not row:
            return
        row.error_code = "EXPORT_GENERATION_FAILED"
        row.error_message = "The report export could not be generated."
        row.lease_owner = None
        row.lease_expires_at = None
        if row.attempt_count < settings.background_job_max_attempts:
            row.status = "PENDING"
            row.next_attempt_at = _now() + timedelta(seconds=min(900, 15 * 2**row.attempt_count))
        else:
            row.status = "FAILED"
            row.completed_at = _now()
            audit(
                db,
                "report.export_failed",
                AuditActor("SYSTEM"),
                "report_export_job",
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
