import hashlib
import json
from typing import Any
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.integrations.employer_portal.models import EmployerSubmission
from app.integrations.employer_portal.schemas import ConvertSubmission, PortalSubmission
from app.modules.demand.models import (
    Contact,
    JobDescriptionVersion,
    Organization,
    Partnership,
    PartnershipDocument,
    Requirement,
    Vacancy,
)
from app.modules.demand.schemas import normalize_phone, normalized_name
from app.modules.external_references.models import ExternalReference
from app.modules.iam.actors import AuthorizationContext
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
    db: Session,
    data: PortalSubmission,
    actor: AuthorizationContext,
    request: Request,
    *,
    commit: bool = True,
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
    if commit:
        db.commit()
    return row, False


def convert(
    db: Session,
    row: EmployerSubmission,
    values: ConvertSubmission,
    actor: Principal,
    request: Request,
) -> EmployerSubmission:
    from app.integrations.intake.service import lock_key

    lock_key(db, "employer-name:" + normalized_name(row.company_name))
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
    from urllib.parse import urlsplit

    duplicate_keys = {
        "employer-phone:" + str(normalize_phone(data.contact_phone)),
        "employer-email:" + str(data.contact_email).casefold(),
    }
    if data.website:
        duplicate_keys.add("employer-domain:" + str(urlsplit(str(data.website)).hostname))
    for key in sorted(duplicate_keys):
        lock_key(db, key)
    organization = (
        db.get(Organization, values.existing_organization_id)
        if values.existing_organization_id
        else None
    )
    if values.existing_organization_id and (not organization or organization.archived_at):
        raise ApiError(404, "ORGANIZATION_NOT_FOUND", "Existing organization not found.")
    candidates = duplicate_candidates(db, data)
    duplicate = bool(candidates)
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
            district_code=data.district,
            industry_code=data.industry,
            address_text=data.address,
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
                partnership_type=data.partnership_type,
                **(
                    {"start_date": data.partnership_start_date}
                    if data.partnership_start_date
                    else {}
                ),
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
                partnership_type=data.partnership_type,
                **(
                    {"start_date": data.partnership_start_date}
                    if data.partnership_start_date
                    else {}
                ),
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
    converted_vacancies = []
    for item in data.vacancies:
        vacancy = Vacancy(
            organization_id=organization.id,
            vacancy_code="VAC-" + uuid4().hex[:12].upper(),
            title=item.job_title,
            status="DRAFT",
            description=item.description,
            location_community=item.location,
            required_headcount=item.openings,
            salary_min=item.salary_min,
            salary_max=item.salary_max,
            salary_frequency=item.salary_frequency,
            work_days_text=item.work_days,
            work_hours_text=item.work_hours,
            accommodation_available=item.accommodation,
            benefits=item.benefits,
            deadline=item.deadline,
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
        for requirement in item.requirements:
            db.add(
                Requirement(
                    vacancy_id=vacancy.id,
                    **requirement.model_dump(),
                    created_by=actor.user.id,
                    source_system="EMPLOYER_PORTAL",
                    created_via="EMPLOYER",
                )
            )
        if item.compensation and item.salary_min is None and item.salary_max is None:
            db.add(
                Requirement(
                    vacancy_id=vacancy.id,
                    criterion_type="WORKING_CONDITION",
                    criterion_key="COMPENSATION_DESCRIPTION",
                    operator="EQ",
                    value_json=item.compensation,
                    is_required=False,
                    weight=0,
                    display_order=9999,
                    created_by=actor.user.id,
                    source_system="EMPLOYER_PORTAL",
                    created_via="EMPLOYER",
                )
            )
        converted_vacancies.append(vacancy)
    db.flush()
    link_intake_documents(db, locked, organization, converted_vacancies, actor, request)
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
    from app.integrations.intake.metrics import employer_converted

    employer_converted.add(1)
    return locked


def duplicate_candidates(db: Session, data: PortalSubmission) -> list[dict[str, Any]]:
    from urllib.parse import urlsplit

    name = normalized_name(data.company_name)
    domain = urlsplit(str(data.website)).hostname if data.website else None
    phone = normalize_phone(data.contact_phone)
    rows = db.scalars(select(Organization).where(Organization.archived_at.is_(None))).all()
    matches = []
    for org in rows:
        reasons = []
        if org.normalized_name == name:
            reasons.append("NAME")
        if domain and org.website and urlsplit(org.website).hostname == domain:
            reasons.append("DOMAIN")
        contacts = db.scalars(
            select(Contact).where(Contact.organization_id == org.id, Contact.archived_at.is_(None))
        ).all()
        if any(c.email and c.email.lower() == str(data.contact_email).lower() for c in contacts):
            reasons.append("EMAIL")
        if phone and any(c.phone_normalized == phone for c in contacts):
            reasons.append("PHONE")
        # Same location alone is not sufficient evidence of an organization duplicate.
        if reasons:
            matches.append({"id": str(org.id), "name": org.name, "reasons": reasons})
        if len(matches) >= 20:
            break
    return matches


def link_intake_documents(
    db: Session,
    submission: EmployerSubmission,
    organization: Organization,
    vacancies: list[Vacancy],
    actor: Principal,
    request: Request,
) -> None:
    from app.integrations.intake.models import IntakeDocument, PublicIntake

    receipt = db.scalar(
        select(PublicIntake).where(PublicIntake.employer_submission_id == submission.id)
    )
    if not receipt:
        return
    partnership = db.scalar(
        select(Partnership)
        .where(Partnership.organization_id == organization.id, Partnership.archived_at.is_(None))
        .order_by(Partnership.created_at.desc())
    )
    assert partnership is not None
    receipt.status = "APPLIED"
    for staged in db.scalars(select(IntakeDocument).where(IntakeDocument.intake_id == receipt.id)):
        if staged.scan_status != "AVAILABLE":
            raise ApiError(
                409,
                "DOCUMENT_SCAN_PENDING",
                "Complete document security scanning before conversion.",
            )
        if staged.linked_document_id:
            continue
        model: type[PartnershipDocument] | type[JobDescriptionVersion]
        if staged.kind == "JD":
            if staged.vacancy_index is None or staged.vacancy_index >= len(vacancies):
                raise ApiError(422, "DOCUMENT_TARGET_INVALID", "Check the job description vacancy.")
            model, field, owner = (
                JobDescriptionVersion,
                "vacancy_id",
                vacancies[staged.vacancy_index].id,
            )
        else:
            model, field, owner = PartnershipDocument, "partnership_id", partnership.id
        version = (
            db.scalar(select(func.max(model.version_number)).where(getattr(model, field) == owner))
            or 0
        ) + 1
        document = model(
            **{field: owner},
            document_code="DOC-" + uuid4().hex.upper(),
            storage_key=staged.storage_key,
            original_filename=staged.original_filename,
            mime_type=staged.mime_type,
            size_bytes=staged.size_bytes,
            sha256=staged.sha256,
            scan_status=staged.scan_status,
            scan_details={"source": "EMPLOYER_INTAKE", "kind": staged.kind},
            version_number=version,
            created_by=actor.user.id,
            source_system="EMPLOYER_PORTAL",
            created_via="EMPLOYER",
        )
        db.add(document)
        db.flush()
        staged.linked_document_id = document.id
        audit(db, "document.intake_linked", actor.audit_actor, "document", document.id, request)
