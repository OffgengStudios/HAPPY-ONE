import hashlib
import json
from typing import Any
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.integrations.employer_portal.auth import EmployerPortalIdentity
from app.integrations.employer_portal.models import EmployerSubmission
from app.integrations.employer_portal.schemas import ConvertSubmission, PortalSubmission
from app.modules.demand.models import Contact, Organization, Partnership, Requirement, Vacancy
from app.modules.demand.schemas import normalize_phone, normalized_name
from app.modules.external_references.models import ExternalReference
from app.modules.iam.dependencies import Principal
from app.modules.iam.models import now
from app.modules.iam.service import audit


def cipher() -> Fernet:
    try:
        return Fernet(settings.identity_encryption_key.get_secret_value().encode())
    except (TypeError, ValueError) as error:
        raise ApiError(
            503,
            "INTEGRATION_ENCRYPTION_NOT_CONFIGURED",
            "Protected integration storage is not configured.",
        ) from error


def payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def encrypt(data: PortalSubmission) -> str:
    raw = json.dumps(data.model_dump(mode="json", by_alias=True), separators=(",", ":")).encode()
    return cipher().encrypt(raw).decode()


def decrypt(row: EmployerSubmission) -> PortalSubmission:
    try:
        raw = cipher().decrypt(row.payload_ciphertext.encode())
        return PortalSubmission.model_validate_json(raw)
    except (InvalidToken, ValueError) as error:
        raise ApiError(
            500, "INTEGRATION_PAYLOAD_UNAVAILABLE", "Protected submission data could not be read."
        ) from error


def view(row: EmployerSubmission, include_payload: bool = False) -> dict[str, Any]:
    result = {
        "id": row.id,
        "submission_id": row.external_submission_id,
        "reference_number": row.reference_number,
        "company_name": row.company_name,
        "vacancy_count": row.vacancy_count,
        "status": row.status,
        "review_notes": row.review_notes,
        "organization_id": row.organization_id,
        "received_at": row.received_at,
        "converted_at": row.converted_at,
        "version": row.version,
    }
    if include_payload:
        result["submission"] = decrypt(row).model_dump(mode="json", by_alias=False)
    return result


def receive(
    db: Session, data: PortalSubmission, actor: EmployerPortalIdentity, request: Request
) -> tuple[EmployerSubmission, bool]:
    serialized = data.model_dump(mode="json", by_alias=True)
    fingerprint = payload_hash(serialized)
    existing = db.scalar(
        select(EmployerSubmission).where(
            EmployerSubmission.external_submission_id == data.submission_id
        )
    )
    if existing:
        if existing.payload_hash != fingerprint:
            raise ApiError(
                409,
                "INTEGRATION_EVENT_CONFLICT",
                "The submission ID was already used with different content.",
            )
        return existing, True
    row = EmployerSubmission(
        external_submission_id=data.submission_id,
        reference_number=data.reference_number,
        payload_hash=fingerprint,
        payload_ciphertext=encrypt(data),
        company_name=data.company_name,
        vacancy_count=len(data.vacancies),
    )
    db.add(row)
    db.flush()
    audit(
        db,
        "employer_portal.submission_received",
        actor.audit_actor,
        "employer_submission",
        row.id,
        request,
        changes={"vacancy_count": row.vacancy_count},
    )
    db.commit()
    return row, False


def convert(
    db: Session,
    row: EmployerSubmission,
    values: ConvertSubmission,
    actor: Principal,
    request: Request,
) -> EmployerSubmission:
    locked = db.scalar(
        select(EmployerSubmission).where(EmployerSubmission.id == row.id).with_for_update()
    )
    assert locked
    if locked.version != values.version:
        raise ApiError(
            409, "RECORD_VERSION_CONFLICT", "This submission changed. Refresh before saving."
        )
    if locked.status not in {"NEW", "NEEDS_REVIEW"}:
        raise ApiError(
            409, "SUBMISSION_NOT_CONVERTIBLE", "Only pending submissions can be converted."
        )
    data = decrypt(locked)
    organization = (
        db.get(Organization, values.existing_organization_id)
        if values.existing_organization_id
        else None
    )
    if values.existing_organization_id and (not organization or organization.archived_at):
        raise ApiError(404, "ORGANIZATION_NOT_FOUND", "Existing organization not found.")
    duplicate = db.scalar(
        select(Organization).where(
            Organization.normalized_name == normalized_name(data.company_name),
            Organization.archived_at.is_(None),
        )
    )
    if not organization and duplicate:
        locked.status = "NEEDS_REVIEW"
        locked.review_notes = "Select the existing organization before conversion."
        locked.version += 1
        db.commit()
        raise ApiError(
            409, "POSSIBLE_DUPLICATE", "Select the existing organization before conversion."
        )
    if not organization:
        organization = Organization(
            organization_code="EMP-" + uuid4().hex[:12].upper(),
            name=data.company_name,
            normalized_name=normalized_name(data.company_name),
            organization_type="EMPLOYER",
            sector_code=data.sector,
            region_code=data.region,
            community=data.city,
            website=str(data.website) if data.website else None,
            created_by=actor.user.id,
            source_system="EMPLOYER_PORTAL",
            created_via="INTEGRATION",
        )
        db.add(organization)
        db.flush()
        db.add(
            Partnership(
                organization_id=organization.id,
                mou_required=values.mou_required,
                created_by=actor.user.id,
                source_system="EMPLOYER_PORTAL",
                created_via="INTEGRATION",
            )
        )
    elif not db.scalar(
        select(Partnership.id).where(Partnership.organization_id == organization.id)
    ):
        db.add(
            Partnership(
                organization_id=organization.id,
                mou_required=values.mou_required,
                created_by=actor.user.id,
                source_system="EMPLOYER_PORTAL",
                created_via="INTEGRATION",
            )
        )
    existing_contact = db.scalar(
        select(Contact).where(
            Contact.organization_id == organization.id,
            Contact.email == str(data.contact_email).lower(),
            Contact.archived_at.is_(None),
        )
    )
    if not existing_contact:
        primary_exists = db.scalar(
            select(Contact.id).where(
                Contact.organization_id == organization.id,
                Contact.is_primary.is_(True),
                Contact.is_active.is_(True),
                Contact.archived_at.is_(None),
            )
        )
        db.add(
            Contact(
                organization_id=organization.id,
                full_name=data.contact_name,
                job_title=data.contact_role,
                phone_raw=data.contact_phone,
                phone_normalized=normalize_phone(data.contact_phone),
                email=str(data.contact_email).lower(),
                is_primary=not bool(primary_exists),
                created_by=actor.user.id,
                source_system="EMPLOYER_PORTAL",
                created_via="INTEGRATION",
            )
        )
    for item in data.vacancies:
        vacancy = Vacancy(
            organization_id=organization.id,
            vacancy_code="VAC-" + uuid4().hex[:12].upper(),
            title=item.job_title,
            status="DRAFT",
            description=item.description,
            location_community=item.location,
            required_headcount=item.openings,
            created_by=actor.user.id,
            source_system="EMPLOYER_PORTAL",
            created_via="INTEGRATION",
        )
        db.add(vacancy)
        db.flush()
        db.add(
            Requirement(
                vacancy_id=vacancy.id,
                criterion_type="EMPLOYMENT",
                criterion_key="EMPLOYMENT_TYPE",
                operator="EQ",
                value_json=item.employment_type,
                is_required=True,
                weight=1,
                display_order=0,
                created_by=actor.user.id,
                source_system="EMPLOYER_PORTAL",
                created_via="INTEGRATION",
            )
        )
    db.flush()
    db.add(
        ExternalReference(
            entity_type="ORGANIZATION",
            entity_id=organization.id,
            external_system="EMPLOYER_PORTAL",
            external_id=data.submission_id,
            external_metadata={"reference_number": data.reference_number},
        )
    )
    locked.status = "CONVERTED"
    locked.organization_id = organization.id
    locked.review_notes = values.reason
    locked.converted_at = now()
    locked.converted_by = actor.user.id
    locked.version += 1
    audit(
        db,
        "employer_portal.submission_converted",
        actor.audit_actor,
        "organization",
        organization.id,
        request,
        changes={"submission_id": data.submission_id, "vacancy_count": len(data.vacancies)},
    )
    db.commit()
    return locked
