import hashlib
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.modules.demand.models import JobDescriptionVersion, PartnershipDocument
from app.modules.supply.files import ScanResult, validate_file
from app.modules.supply.files import scan as scan_file
from app.storage.s3 import get_storage_client

PrivateDocument = PartnershipDocument | JobDescriptionVersion


def scan(data: bytes) -> ScanResult:
    return scan_file(data)


def upload(
    db: Session,
    model: type[PrivateDocument],
    owner_field: str,
    owner_id: UUID,
    prefix: str,
    data: bytes,
    filename: str,
    declared: str,
    actor_id: UUID,
) -> PrivateDocument:
    name, mime = validate_file(data, filename, declared)
    result = scan(data)
    owner_column = getattr(model, owner_field)
    version_number = (
        db.scalar(select(func.max(model.version_number)).where(owner_column == owner_id)) or 0
    ) + 1
    document = model(
        **{owner_field: owner_id},
        document_code="DOC-" + uuid4().hex.upper(),
        storage_key=f"{prefix}/{owner_id}/{uuid4().hex}",
        original_filename=name,
        mime_type=mime,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        version_number=version_number,
        scan_status=result,
        scan_details={"provider": "clamd" if settings.file_scan_host else "unconfigured"},
        created_by=actor_id,
    )
    if result != "REJECTED":
        try:
            get_storage_client().put_object(
                Bucket=settings.s3_bucket,
                Key=document.storage_key,
                Body=data,
                ContentType=mime,
            )
        except Exception:
            raise ApiError(
                503, "STORAGE_UNAVAILABLE", "Private storage is unavailable. Retry the upload."
            ) from None
    db.add(document)
    return document


def verified_bytes(document: PrivateDocument) -> bytes:
    try:
        result = get_storage_client().get_object(
            Bucket=settings.s3_bucket, Key=document.storage_key
        )
        body = result["Body"]
        try:
            data = body.read(settings.file_max_bytes + 1)
        finally:
            body.close()
        if len(data) != document.size_bytes or hashlib.sha256(data).hexdigest() != document.sha256:
            raise ValueError("Stored file integrity mismatch")
        return data
    except Exception:
        raise ApiError(
            503,
            "STORAGE_UNAVAILABLE",
            "The stored document could not be verified. Contact an administrator.",
        ) from None


def public_view(document: PrivateDocument) -> dict[str, Any]:
    return {
        "id": str(document.id),
        "version": document.version,
        "document_code": document.document_code,
        "original_filename": document.original_filename,
        "mime_type": document.mime_type,
        "size_bytes": document.size_bytes,
        "version_number": document.version_number,
        "scan_status": document.scan_status,
        "created_at": document.created_at.isoformat(),
        "archived_at": document.archived_at.isoformat() if document.archived_at else None,
    }
