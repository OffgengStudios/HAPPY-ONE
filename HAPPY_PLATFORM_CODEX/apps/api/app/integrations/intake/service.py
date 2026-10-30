import hashlib
import json
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.integrations.cv_parser import get_cv_parser
from app.integrations.employer_portal.service import cipher
from app.integrations.intake import metrics
from app.integrations.intake.models import IntakeDocument, PublicIntake
from app.integrations.intake.schemas import ParticipantSubmission
from app.integrations.intake.sources import PARTICIPANT_SOURCE
from app.modules.cv_parser import service as parsing
from app.modules.demand.schemas import normalize_phone
from app.modules.external_references.models import ExternalReference
from app.modules.iam.actors import AuditActor
from app.modules.iam.models import LoginThrottle, now
from app.modules.iam.security import digest
from app.modules.iam.service import audit, check_origin
from app.modules.supply import files, schemas
from app.modules.supply import service as supply
from app.modules.supply.models import (
    Consent,
    Document,
    Education,
    Experience,
    Participant,
    Person,
    SensitiveProfile,
    Skill,
)
from app.storage.s3 import get_storage_client


class PublicActor:
    permissions: set[str] = set()
    audit_actor = AuditActor("INTEGRATION", PARTICIPANT_SOURCE + "_PUBLIC")


def protect(db: Session, request: Request) -> None:
    check_origin(request)
    # Shared PostgreSQL counters work across API processes. Never trust X-Forwarded-For
    # from the caller; only the configured trusted proxy may set request.client.
    host = request.client.host if request.client else "unknown"
    key = digest("public-intake:" + request.url.path + ":" + host)
    db.execute(
        insert(LoginThrottle)
        .values(key=key, attempts=0, expires_at=now() + timedelta(minutes=15))
        .on_conflict_do_nothing()
    )
    bucket = db.scalar(select(LoginThrottle).where(LoginThrottle.key == key).with_for_update())
    assert bucket is not None
    if bucket.expires_at <= now():
        bucket.attempts = 0
        bucket.expires_at = now() + timedelta(minutes=15)
    allowed = bucket.attempts < settings.public_intake_limit
    bucket.attempts += 1
    db.commit()
    if not allowed:
        raise ApiError(429, "RATE_LIMITED", "Too many submissions. Please try again later.")


def lock_key(db: Session, value: str) -> None:
    number = int.from_bytes(hashlib.sha256(value.encode()).digest()[:8], "big", signed=True)
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": number})


def submitted_payload(data: ParticipantSubmission) -> dict[str, Any]:
    # SecretStr masks normal serialization. Only this encrypted-evidence boundary
    # unwraps the value; never use it in logs, audits or public responses.
    payload = data.model_dump(mode="json")
    if data.identity:
        payload["identity"]["government_id"] = data.identity.government_id.get_secret_value()
    return payload


def receipt(
    db: Session,
    source: str,
    identifier: UUID,
    payload: dict[str, Any],
    uploads: list[tuple[str, str, bytes]],
) -> tuple[PublicIntake, bool]:
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "payload": payload,
                "files": [
                    {"name": n, "mime": m, "sha256": hashlib.sha256(b).hexdigest()}
                    for n, m, b in uploads
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    lock_key(db, source + ":" + str(identifier))
    existing = db.scalar(
        select(PublicIntake).where(
            PublicIntake.source == source, PublicIntake.submission_id == identifier
        )
    )
    if existing:
        if existing.payload_hash != fingerprint:
            raise ApiError(
                409, "SUBMISSION_CONFLICT", "Use a new submission ID for changed content."
            )
        return existing, True
    row = PublicIntake(
        source=source,
        submission_id=identifier,
        payload_hash=fingerprint,
        payload_ciphertext=cipher()
        .encrypt(json.dumps(payload, separators=(",", ":")).encode())
        .decode(),
    )
    db.add(row)
    db.flush()
    return row, False


def upload_stage(
    db: Session,
    row: PublicIntake,
    kind: str,
    upload: tuple[str, str, bytes],
    created_keys: list[str],
    vacancy_index: int | None = None,
) -> IntakeDocument:
    filename, declared, content = upload
    name, mime = files.validate_file(content, filename, declared)
    status = files.scan(content)
    if status == "REJECTED":
        metrics.scan_failures.add(1)
        raise ApiError(
            422, "DOCUMENT_REJECTED", "The uploaded document did not pass security checks."
        )
    key = f"intakes/{row.id}/{uuid4().hex}"
    try:
        get_storage_client().put_object(
            Bucket=settings.s3_bucket, Key=key, Body=content, ContentType=mime
        )
    except Exception:
        raise ApiError(
            503, "STORAGE_UNAVAILABLE", "Private storage is unavailable. Retry this submission."
        ) from None
    created_keys.append(key)
    document = IntakeDocument(
        intake_id=row.id,
        kind=kind,
        vacancy_index=vacancy_index,
        storage_key=key,
        original_filename=name,
        mime_type=mime,
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        scan_status=status,
    )
    db.add(document)
    db.flush()
    return document


def compensate(db: Session, keys: list[str]) -> None:
    db.rollback()
    for key in keys:
        try:
            get_storage_client().delete_object(Bucket=settings.s3_bucket, Key=key)
        except Exception:
            # Preserve an operational signal without exposing private object keys.
            import logging

            logging.getLogger("happy.intake").error("intake_storage_cleanup_failed")


def apply_participant(
    db: Session,
    receipt_row: PublicIntake,
    data: ParticipantSubmission,
    request: Request,
    staged: IntakeDocument | None,
) -> Participant | None:
    actor = PublicActor()
    profile = {**data.basic.model_dump(), **data.contact.model_dump()}
    conflict_keys = {
        "participant-phone:" + str(normalize_phone(data.contact.phone_raw)),
        "participant-location:" + data.contact.community.casefold().strip(),
    }
    if data.contact.email:
        conflict_keys.add("participant-email:" + str(data.contact.email).casefold())
    fingerprint = None
    if data.identity:
        fingerprint = supply.identity_hash(
            data.identity.government_id_type, data.identity.government_id.get_secret_value()
        )
        conflict_keys.add("participant-identity:" + fingerprint)
    for key in sorted(conflict_keys):
        lock_key(db, key)
    identity_match = (
        db.scalar(select(Person.id).where(Person.government_id_hash == fingerprint))
        if fingerprint
        else None
    )
    if identity_match or supply.duplicates(db, profile):
        receipt_row.status = "NEEDS_REVIEW"
        metrics.duplicate_reviews.add(1)
        audit(
            db,
            "participant_intake.duplicate_review_required",
            actor.audit_actor,
            "public_intake",
            receipt_row.id,
            request,
        )
        return None
    row = supply.create(
        db,
        schemas.Intake(**profile, implementing_partner=data.implementing_partner),
        actor,
        request,
        commit=False,
    )
    person = db.get(Person, row.person_id)
    assert person is not None
    for record in (row, person):
        record.source_system = PARTICIPANT_SOURCE
        record.created_via = "PARTICIPANT"
    sections: list[tuple[str, Any]] = []
    if data.demographics:
        sections.append(("demographics", data.demographics))
    if data.education:
        sections.append(
            ("education", schemas.EducationWrite(version=row.version, items=data.education))
        )
    if data.employment:
        sections.append(("employment", data.employment))
    if data.training_summary or data.training_interests:
        sections.append(
            (
                "training",
                schemas.TrainingWrite(
                    version=row.version,
                    training_summary=data.training_summary,
                    training_interests=data.training_interests,
                ),
            )
        )
    for name, values in sections:
        supply.section_write(db, row, name, values, actor, request, commit=False)
    supply.record_consent(
        db,
        row,
        schemas.ConsentWrite(
            version=row.version,
            consent_type="PROGRAMME",
            consented_at=now(),
            method="DIGITAL",
            privacy_notice_version=data.consent.notice_version,
            participant_agreed=True,
        ),
        actor,
        request,
        commit=False,
    )
    if data.sensitive:
        supply.save_sensitive(db, row, data.sensitive, actor, request, commit=False)
    if data.identity:
        supply.save_identity(db, row, data.identity, actor, request, commit=False)
    # These children belong to the participant just created in this transaction.
    # Retain participant provenance rather than the staff service's defaults.
    db.flush()
    for model in (Consent, Education, Experience, Skill, SensitiveProfile):
        db.execute(
            update(model)
            .where(model.participant_id == row.id)
            .values(source_system=PARTICIPANT_SOURCE, created_via="PARTICIPANT")
        )
    if staged:
        document = Document(
            participant_id=row.id,
            document_code="DOC-" + uuid4().hex.upper(),
            storage_key=staged.storage_key,
            original_filename=staged.original_filename,
            mime_type=staged.mime_type,
            size_bytes=staged.size_bytes,
            sha256=staged.sha256,
            version_number=1,
            scan_status=staged.scan_status,
            source_system=PARTICIPANT_SOURCE,
            created_via="PARTICIPANT",
            scan_details={"provider": "clamd" if settings.file_scan_host else "unconfigured"},
        )
        db.add(document)
        db.flush()
        staged.linked_document_id = document.id
        row.cv_status = "UPLOADED"
        audit(
            db,
            "document.uploaded",
            actor.audit_actor,
            "document",
            document.id,
            request,
            changes={"scan_status": document.scan_status},
        )
        if document.scan_status == "AVAILABLE":
            parsing.start_job(db, document, row, actor, request, get_cv_parser(), commit=False)
    supply.section_write(
        db,
        row,
        "review",
        schemas.ReviewWrite(version=row.version, reviewed=True),
        actor,
        request,
        commit=False,
    )
    db.flush()
    progress = supply.checklist(db, row)
    # Registration may precede complete Supply onboarding. Preserve the actual
    # checklist; only the existing policy gate may mark onboarding complete.
    if (
        progress["policy_configured"]
        and not progress["missing_sections"]
        and not progress["missing_fields"]
    ):
        supply.complete(
            db,
            row,
            schemas.Complete(version=row.version, completion_mode="SELF_REPORTED"),
            actor,
            request,
            commit=False,
        )
    if row.onboarding_status == "COMPLETE":
        metrics.participant_completed.add(1)
    db.add(
        ExternalReference(
            entity_type="PARTICIPANT",
            entity_id=row.id,
            external_system=PARTICIPANT_SOURCE,
            external_id=str(data.submission_id),
        )
    )
    receipt_row.participant_id = row.id
    receipt_row.status = "APPLIED"
    audit(
        db,
        "participant_intake.submitted",
        actor.audit_actor,
        "participant",
        row.id,
        request,
        changes={"receipt_id": str(receipt_row.id)},
    )
    return row


def public_receipt(row: PublicIntake) -> dict[str, Any]:
    # Identical public responses for new and duplicate records prevent enumeration.
    return {"receipt_id": str(row.id), "status": "RECEIVED"}
