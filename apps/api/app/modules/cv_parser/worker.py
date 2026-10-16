import os
import socket
import time
from datetime import timedelta

from sqlalchemy import or_, select

from app.core.config import settings
from app.db.session import get_session_factory
from app.integrations.cv_parser import get_cv_parser
from app.modules.cv_parser.models import ParserJob
from app.modules.cv_parser.service import process_job
from app.modules.iam.models import now
from app.modules.supply.models import Document, Participant

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def run_once() -> bool:
    with get_session_factory()() as db:
        job = db.scalar(
            select(ParserJob)
            .where(
                ParserJob.status.in_(["QUEUED", "RUNNING"]),
                or_(ParserJob.next_attempt_at.is_(None), ParserJob.next_attempt_at <= now()),
                or_(ParserJob.lease_expires_at.is_(None), ParserJob.lease_expires_at < now()),
                ParserJob.attempt_count < settings.cv_parser_max_attempts,
                ParserJob.archived_at.is_(None),
            )
            .order_by(ParserJob.created_at, ParserJob.id)
            .with_for_update(skip_locked=True)
        )
        if not job:
            return False
        job.status = "RUNNING"
        job.attempt_count += 1
        job.started_at = job.started_at or now()
        job.lease_owner = WORKER_ID
        job.lease_expires_at = now() + timedelta(minutes=5)
        db.commit()
        document = db.get(Document, job.document_id)
        participant = db.get(Participant, document.participant_id) if document else None
        if not document or not participant:
            job.status = "FAILED"
            job.error_code = "SOURCE_NOT_FOUND"
            job.error_message = "The source CV or participant no longer exists."
            job.completed_at = now()
            job.lease_owner = None
            job.lease_expires_at = None
            db.commit()
            return True
        process_job(db, job, document, participant, get_cv_parser())
        if job.status == "FAILED" and job.attempt_count < settings.cv_parser_max_attempts:
            job.status = "QUEUED"
            job.completed_at = None
            job.next_attempt_at = now() + timedelta(seconds=min(900, 15 * 2**job.attempt_count))
            db.commit()
        return True


def main() -> None:
    while True:
        if not run_once():
            time.sleep(2)


if __name__ == "__main__":
    main()
