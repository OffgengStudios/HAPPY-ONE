import hashlib
import hmac
from datetime import date
from difflib import SequenceMatcher
from typing import Any
from uuid import UUID, uuid4

from cryptography.fernet import Fernet
from fastapi import Request
from sqlalchemy import false, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.modules.demand.schemas import Version, normalize_phone, normalized_name
from app.modules.demand.service import assignable, changed, get_record, writable
from app.modules.iam.actors import AuthorizationContext, staff_user_id
from app.modules.iam.models import now
from app.modules.iam.service import audit
from app.modules.supply import schemas as s
from app.modules.supply.ages import event_age, programme_today
from app.modules.supply.models import (
    Consent,
    Document,
    Education,
    Experience,
    OnboardingRevision,
    Participant,
    Person,
    SensitiveProfile,
    Skill,
)

PERSON_PUBLIC = (
    "first_name",
    "surname",
    "other_names",
    "phone_raw",
    "phone_normalized",
    "email",
    "region_code",
    "district_code",
    "community",
    "directions",
    "location_status",
)
PART_PUBLIC = (
    "participant_code",
    "source_system",
    "created_via",
    "person_id",
    "programme_code",
    "implementing_partner",
    "onboarding_date",
    "support_type",
    "source_type",
    "source_detail",
    "onboarding_status",
    "readiness_status",
    "availability_status",
    "cv_status",
    "assigned_user_id",
    "owner_assigned_at",
    "employment_status",
    "current_occupation",
    "sector_code",
    "industry_code",
    "job_type",
    "job_role",
    "work_region_code",
    "work_district_code",
    "work_community",
    "priority",
    "next_action",
    "next_action_due_at",
    "training_summary",
    "training_interests",
    "completion_mode",
    "assisted_by",
    "completed_at",
    "current_cv_id",
)
CHILD_FIELDS: dict[type[Any], tuple[str, ...]] = {
    Education: tuple(s.EducationFields.model_fields),
    Experience: tuple(s.ExperienceFields.model_fields),
    Skill: tuple(s.SkillFields.model_fields),
    Consent: (
        "consent_type",
        "status",
        "consented_at",
        "withdrawn_at",
        "method",
        "privacy_notice_version",
    ),
    Document: (
        "document_code",
        "original_filename",
        "mime_type",
        "size_bytes",
        "version_number",
        "scan_status",
    ),
}


def fields(row: Any, names: tuple[str, ...]) -> dict[str, Any]:
    return {key: getattr(row, key) for key in names}


def child_view(row: Any) -> dict[str, Any]:
    return {
        **fields(row, CHILD_FIELDS[type(row)]),
        "id": row.id,
        "version": row.version,
        "created_at": row.created_at,
        "archived_at": row.archived_at,
    }


def full_name(person: Person) -> str:
    return " ".join(v for v in (person.first_name, person.other_names, person.surname) if v)


def age(birth: date | None, today: date | None = None) -> int | None:
    if not birth:
        return None
    return event_age(birth, today or programme_today())


def required_consent(db: Session, participant: Participant) -> bool:
    if not settings.supply_privacy_notice_version:
        return False
    return (
        db.scalar(
            select(Consent.id)
            .where(
                Consent.participant_id == participant.id,
                Consent.consent_type == "PROGRAMME",
                Consent.status == "ACTIVE",
                Consent.privacy_notice_version == settings.supply_privacy_notice_version,
            )
            .limit(1)
        )
        is not None
    )


def checklist(
    db: Session,
    row: Participant,
    *,
    person: Person | None = None,
    consent_active: bool | None = None,
) -> dict[str, Any]:
    required = set(settings.supply_required_sections) | {"basic", "contact", "consent"}
    if not required <= set(s.SECTIONS):
        raise ApiError(
            503,
            "ONBOARDING_POLICY_INVALID",
            "An administrator must correct the required onboarding sections.",
        )
    completed = set(row.completed_sections)
    field_names = set(settings.supply_required_fields) | {"ghana_card"}
    profile = db.scalar(select(SensitiveProfile).where(SensitiveProfile.participant_id == row.id))
    if profile and str(profile.refugee_status).upper() == "YES":
        field_names.add("nationality")
    if profile and str(profile.disability_status).upper() == "YES":
        field_names.add("disability_specify")
    person_fields = set(PERSON_PUBLIC) | {"date_of_birth", "sex", "nationality"}
    participant_fields = {
        "implementing_partner",
        "onboarding_date",
        "support_type",
        "employment_status",
        "current_occupation",
        "sector_code",
        "industry_code",
        "job_type",
        "job_role",
        "work_region_code",
        "work_district_code",
        "work_community",
        "training_summary",
    }
    if not field_names <= person_fields | participant_fields | {
        "government_id",
        "ghana_card",
        "disability_specify",
    }:
        raise ApiError(503, "ONBOARDING_POLICY_INVALID", "Correct the required onboarding fields.")
    person = person or get_record(db, Person, row.person_id)
    missing_fields = sorted(
        name
        for name in field_names
        if not (
            (person.government_id_ciphertext if person.government_id_type == "GHANA_CARD" else None)
            if name in {"government_id", "ghana_card"}
            else profile.disability_specify
            if name == "disability_specify" and profile
            else getattr(person if name in person_fields else row, name)
        )
    )
    if required_consent(db, row) if consent_active is None else consent_active:
        completed.add("consent")
    else:
        completed.discard("consent")
    if row.cv_status in {"READY", "NOT_REQUIRED"}:
        completed.add("cv")
    else:
        completed.discard("cv")
    missing = sorted(required - completed)
    return {
        "required_sections": sorted(required),
        "completed_sections": sorted(completed),
        "missing_sections": missing,
        "missing_fields": missing_fields,
        "required_fields": sorted(field_names),
        "policy_configured": bool(
            settings.supply_onboarding_policy_approved and settings.supply_privacy_notice_version
        ),
        "profile_completion_pct": round(
            (len(required & completed) + len(field_names) - len(missing_fields))
            / (len(required) + len(field_names))
            * 100,
            2,
        ),
        "notice_configured": bool(settings.supply_privacy_notice_version),
        "privacy_notice_version": settings.supply_privacy_notice_version or None,
    }


def assert_submission_eligible(db: Session, row: Participant) -> None:
    progress = checklist(db, row)
    if (
        row.archived_at
        or row.onboarding_status != "COMPLETE"
        or not progress["policy_configured"]
        or progress["missing_sections"]
        or progress["missing_fields"]
    ):
        raise ApiError(
            422, "ONBOARDING_INCOMPLETE", "Complete required onboarding before employer submission."
        )
    if not required_consent(db, row):
        raise ApiError(
            422, "CONSENT_REQUIRED", "Record active consent for the current privacy notice."
        )


def participant_view(
    db: Session,
    row: Participant,
    *,
    person: Person | None = None,
    consent_active: bool | None = None,
) -> dict[str, Any]:
    person = person or get_record(db, Person, row.person_id)
    if consent_active is None:
        consent_active = required_consent(db, row)
    progress = checklist(db, row, person=person, consent_active=consent_active)
    eligible = (
        not row.archived_at
        and row.onboarding_status == "COMPLETE"
        and not progress["missing_sections"]
        and not progress["missing_fields"]
        and progress["policy_configured"]
        and consent_active
    )
    return {
        **fields(person, PERSON_PUBLIC),
        **fields(row, PART_PUBLIC),
        **progress,
        "id": row.id,
        "version": row.version,
        "full_name": full_name(person),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "archived_at": row.archived_at,
        "submission_eligible": eligible,
    }


def participant_views(db: Session, rows: list[Participant]) -> list[dict[str, Any]]:
    if not rows:
        return []
    people = {
        person.id: person
        for person in db.scalars(
            select(Person).where(Person.id.in_({row.person_id for row in rows}))
        )
    }
    consenting = (
        set(
            db.scalars(
                select(Consent.participant_id).where(
                    Consent.participant_id.in_({row.id for row in rows}),
                    Consent.consent_type == "PROGRAMME",
                    Consent.status == "ACTIVE",
                    Consent.privacy_notice_version == settings.supply_privacy_notice_version,
                )
            )
        )
        if settings.supply_privacy_notice_version
        else set()
    )
    return [
        participant_view(db, row, person=people[row.person_id], consent_active=row.id in consenting)
        for row in rows
    ]


def lock(db: Session, identifier: UUID, version: int) -> Participant:
    row = get_record(db, Participant, identifier, True)
    writable(row, version)
    return row


def save(
    db: Session,
    row: Participant,
    principal: AuthorizationContext,
    request: Request,
    event: str,
    details: dict[str, Any] | None = None,
    *,
    commit: bool = True,
) -> None:
    db.flush()
    audit(db, event, principal.audit_actor, "participants", row.id, request, changes=details or {})
    if commit:
        db.commit()


def identity_hash(kind: str, raw: str) -> str:
    key = settings.identity_lookup_key.get_secret_value()
    if len(key) < 32:
        raise ApiError(
            503,
            "IDENTITY_STORAGE_NOT_CONFIGURED",
            "An administrator must configure protected identity storage.",
        )
    normalized = "".join(c for c in raw.upper() if c.isalnum())
    return hmac.new(key.encode(), (kind + ":" + normalized).encode(), hashlib.sha256).hexdigest()


def duplicates(
    db: Session, values: dict[str, Any], exclude: UUID | None = None
) -> list[dict[str, Any]]:
    phone = normalize_phone(values.get("phone_raw"))
    name = normalized_name(
        " ".join(str(values.get(k) or "") for k in ("first_name", "other_names", "surname"))
    )
    email = str(values.get("email") or "").lower()
    community = normalized_name(str(values.get("community") or ""))
    query = select(Participant, Person).join(Person, Participant.person_id == Person.id)
    if exclude:
        query = query.where(Participant.id != exclude)
    # Fuzzy names inspect the same community; phone/email matches ignore location.
    query = query.where(
        or_(
            Person.phone_normalized == phone,
            Person.email == email if email else false(),
            func.lower(func.regexp_replace(func.trim(Person.community), r"\s+", " ", "g"))
            == community
            if community
            else Person.id.is_(None),
        )
    )
    matches = []
    for row, person in db.execute(query):
        reasons = []
        if phone and person.phone_normalized == phone:
            reasons.append("PHONE")
        if email and person.email == email:
            reasons.append("EMAIL")
        if (
            name
            and community == normalized_name(person.community)
            and SequenceMatcher(None, name, person.normalized_name).ratio() >= 0.9
        ):
            reasons.append("NAME_LOCATION")
        if reasons:
            matches.append(
                {
                    "id": row.id,
                    "participant_code": row.participant_code,
                    "full_name": full_name(person),
                    "archived": bool(row.archived_at),
                    "reasons": reasons,
                }
            )
        if len(matches) >= 20:
            break
    return matches


def check_duplicate(
    db: Session, data: dict[str, Any], exclude: UUID | None, acknowledged: bool
) -> None:
    if duplicates(db, data, exclude) and not acknowledged:
        raise ApiError(
            409,
            "DUPLICATE_SUSPECTED",
            "Review duplicate matches or acknowledge this is a distinct person.",
        )


def create(
    db: Session,
    data: s.Intake,
    principal: AuthorizationContext,
    request: Request,
    *,
    commit: bool = True,
) -> Participant:
    values = data.model_dump()
    check_duplicate(db, values, None, data.duplicate_acknowledged)
    assignable(db, data.assigned_user_id, "participant:edit")
    person = Person(
        **{
            k: v
            for k, v in values.items()
            if k in s.Basic.model_fields or k in s.Contact.model_fields
        },
        phone_normalized=normalize_phone(data.phone_raw),
        normalized_name=normalized_name(
            " ".join(v for v in (data.first_name, data.other_names, data.surname) if v)
        ),
        created_by=staff_user_id(principal),
    )
    if person.email:
        person.email = person.email.lower()
    db.add(person)
    db.flush()
    row = Participant(
        person_id=person.id,
        participant_code=f"HAPPY-{now().year}-{uuid4().hex[:16].upper()}",
        assigned_user_id=data.assigned_user_id,
        owner_assigned_at=now() if data.assigned_user_id else None,
        source_type=data.source_type,
        source_detail=data.source_detail,
        implementing_partner=data.implementing_partner,
        onboarding_date=data.onboarding_date,
        support_type=data.support_type,
        completed_sections=["basic", "contact"],
        created_by=staff_user_id(principal),
    )
    db.add(row)
    save(
        db,
        row,
        principal,
        request,
        "participant.created",
        {"duplicate_acknowledged": data.duplicate_acknowledged},
        commit=commit,
    )
    return row


def replace_children(
    db: Session,
    row: Participant,
    model: type[Any],
    entries: list[dict[str, Any]],
    actor: UUID | None,
) -> None:
    for child in db.scalars(
        select(model).where(model.participant_id == row.id, model.archived_at.is_(None))
    ):
        child.archived_at = now()
        changed(child, actor)
    for entry in entries:
        db.add(model(participant_id=row.id, created_by=actor, **entry))


SECTION_SCHEMAS: dict[str, type[Version]] = {
    "basic": s.BasicWrite,
    "contact": s.ContactWrite,
    "demographics": s.Demographics,
    "education": s.EducationWrite,
    "employment": s.EmploymentWrite,
    "training": s.TrainingWrite,
    "review": s.ReviewWrite,
}


def section_write(
    db: Session,
    row: Participant,
    section: str,
    data: Version,
    principal: AuthorizationContext,
    request: Request,
    *,
    commit: bool = True,
) -> None:
    if row.onboarding_status == "WITHDRAWN":
        raise ApiError(
            409, "PARTICIPANT_WITHDRAWN", "Reopen onboarding with a reason before editing sections."
        )
    person = get_record(db, Person, row.person_id, True)
    values = data.model_dump(exclude={"version", "duplicate_acknowledged"})
    reference = values.get("onboarding_date", row.onboarding_date)
    birth = values.get("date_of_birth", person.date_of_birth)
    if reference and birth and reference < birth:
        raise ApiError(422, "EVENT_BEFORE_BIRTH", "Onboarding date cannot precede date of birth.")
    if section == "demographics" and birth:
        from app.modules.placement.models import Placement
        from app.modules.training.models import Training, TrainingAttendance

        early_training = db.scalar(
            select(Training.id)
            .join(TrainingAttendance)
            .where(TrainingAttendance.participant_id == row.id, Training.start_date < birth)
        )
        early_placement = db.scalar(
            select(Placement.id).where(
                Placement.participant_id == row.id, Placement.actual_start_date < birth
            )
        )
        if early_training or early_placement:
            raise ApiError(422, "EVENT_BEFORE_BIRTH", "Date of birth is after an existing event.")
    if section in {"basic", "demographics"}:
        db.add(
            OnboardingRevision(
                participant_id=row.id,
                created_by=staff_user_id(principal),
                previous_json={
                    "onboarding_date": str(row.onboarding_date) if row.onboarding_date else None,
                    "date_of_birth": str(person.date_of_birth) if person.date_of_birth else None,
                },
            )
        )
    if section in {"basic", "contact"}:
        check_duplicate(
            db,
            {**fields(person, PERSON_PUBLIC), **values},
            row.id,
            bool(getattr(data, "duplicate_acknowledged", False)),
        )
        for key, value in values.items():
            setattr(
                person if key in s.Basic.model_fields or key in s.Contact.model_fields else row,
                key,
                value,
            )
        person.phone_normalized = normalize_phone(person.phone_raw) or ""
        person.email = person.email.lower() if person.email else None
        person.normalized_name = normalized_name(full_name(person))
        changed(person, staff_user_id(principal))
    elif section == "demographics":
        for key, value in values.items():
            setattr(person, key, value)
        changed(person, staff_user_id(principal))
    elif section == "education":
        replace_children(db, row, Education, values["items"], staff_user_id(principal))
    elif section == "employment":
        replace_children(db, row, Experience, values.pop("experience"), staff_user_id(principal))
        replace_children(db, row, Skill, values.pop("skills"), staff_user_id(principal))
        for key, value in values.items():
            setattr(row, key, value)
    elif section == "training":
        row.training_summary = values["training_summary"]
        if values.get("training_interests") is not None:
            row.training_interests = values["training_interests"]
    completed = set(row.completed_sections)
    if section != "review":
        completed.discard("review")
    row.completed_sections = sorted(completed | {section})
    row.onboarding_status = "IN_PROGRESS"
    changed(row, staff_user_id(principal))
    save(
        db,
        row,
        principal,
        request,
        "participant.updated",
        {"section": section, "fields": list(values)},
        commit=commit,
    )


def record_consent(
    db: Session,
    row: Participant,
    data: s.ConsentWrite,
    principal: AuthorizationContext,
    request: Request,
    *,
    commit: bool = True,
) -> Consent:
    if row.onboarding_status == "WITHDRAWN":
        raise ApiError(
            409, "PARTICIPANT_WITHDRAWN", "Reopen onboarding before recording new consent."
        )
    if data.consent_type == "PROGRAMME" and (
        not settings.supply_privacy_notice_version
        or data.privacy_notice_version != settings.supply_privacy_notice_version
    ):
        raise ApiError(
            422,
            "PRIVACY_NOTICE_REQUIRED",
            "Configure and use the approved programme privacy notice version.",
        )
    # A new consent is a new historical record; never overwrite an earlier withdrawal.
    consent = Consent(
        participant_id=row.id,
        created_by=staff_user_id(principal),
        **data.model_dump(exclude={"version", "participant_agreed"}),
    )
    db.add(consent)
    changed(row, staff_user_id(principal))
    save(
        db,
        row,
        principal,
        request,
        "participant.consent_recorded",
        {"consent_type": data.consent_type, "privacy_notice_version": data.privacy_notice_version},
        commit=commit,
    )
    return consent


def withdraw_consent(
    db: Session,
    row: Participant,
    consent: Consent,
    reason: str,
    principal: AuthorizationContext,
    request: Request,
) -> None:
    if consent.status != "ACTIVE":
        raise ApiError(409, "CONSENT_ALREADY_WITHDRAWN", "This consent was already withdrawn.")
    # Withdraw all active records of this type, so an earlier grant cannot revive processing.
    for grant in db.scalars(
        select(Consent)
        .where(
            Consent.participant_id == row.id,
            Consent.consent_type == consent.consent_type,
            Consent.status == "ACTIVE",
        )
        .with_for_update()
    ):
        grant.status = "WITHDRAWN"
        grant.withdrawn_at = now()
        grant.reason = reason
        changed(grant, staff_user_id(principal))
    if consent.consent_type == "PROGRAMME" and row.onboarding_status == "COMPLETE":
        row.onboarding_status = "BLOCKED"
    changed(row, staff_user_id(principal))
    save(
        db,
        row,
        principal,
        request,
        "participant.consent_withdrawn",
        {"consent_type": consent.consent_type, "reason": reason},
    )


def complete(
    db: Session,
    row: Participant,
    data: s.Complete,
    principal: AuthorizationContext,
    request: Request,
    *,
    commit: bool = True,
) -> None:
    if row.onboarding_status in {"COMPLETE", "WITHDRAWN"}:
        raise ApiError(
            409, "INVALID_STATUS_TRANSITION", "Reopen onboarding before completing it again."
        )
    progress = checklist(db, row)
    if not progress["policy_configured"]:
        raise ApiError(
            422, "ONBOARDING_POLICY_REQUIRED", "Approved onboarding policy is not configured."
        )
    if not required_consent(db, row):
        raise ApiError(
            422, "CONSENT_REQUIRED", "Record active consent for the approved privacy notice."
        )
    if progress["missing_sections"] or progress["missing_fields"]:
        raise ApiError(
            422, "ONBOARDING_INCOMPLETE", "Complete the missing required onboarding sections."
        )
    profile = db.scalar(select(SensitiveProfile).where(SensitiveProfile.participant_id == row.id))
    if profile is None:
        profile = SensitiveProfile(participant_id=row.id, created_by=staff_user_id(principal))
        db.add(profile)
    if profile.baseline_captured_at is None:
        row.baseline_employment_status = row.employment_status
        row.baseline_occupation = row.current_occupation
        profile.baseline_income_amount = profile.current_income_amount
        profile.baseline_income_frequency = profile.income_frequency
        profile.baseline_income_status = profile.income_status or (
            "KNOWN" if profile.current_income_amount is not None else "NOT_RECORDED"
        )
        profile.baseline_captured_at = now()
    row.onboarding_status = "COMPLETE"
    row.completion_mode = data.completion_mode
    row.assisted_by = staff_user_id(principal) if data.completion_mode == "STAFF_ASSISTED" else None
    row.completed_at = now()
    changed(row, staff_user_id(principal))
    save(
        db,
        row,
        principal,
        request,
        "participant.onboarding_completed",
        {
            "mode": data.completion_mode,
            "required_sections": sorted(
                set(settings.supply_required_sections) | {"basic", "contact", "consent"}
            ),
        },
        commit=commit,
    )


def sensitive_view(db: Session, row: Participant) -> dict[str, Any]:
    person = get_record(db, Person, row.person_id)
    profile = db.scalar(select(SensitiveProfile).where(SensitiveProfile.participant_id == row.id))
    names = tuple(k for k in s.SensitiveWrite.model_fields if k != "version")
    return {
        **fields(person, ("date_of_birth", "sex", "nationality", "government_id_type")),
        **(fields(profile, names) if profile else {k: None for k in names}),
        "age": age(person.date_of_birth),
        "current_age": age(person.date_of_birth),
        "age_at_onboarding": event_age(person.date_of_birth, row.onboarding_date),
        "onboarding_age_projected": bool(
            row.onboarding_date and row.onboarding_date > programme_today()
        ),
        "age_reference_date": programme_today(),
        "age_category": None,
        "age_category_status": "PENDING_PROGRAMME_RULE",
        "has_ghana_card": bool(
            person.government_id_type == "GHANA_CARD" and person.government_id_ciphertext
        ),
        "has_voter_id": bool(person.voter_id_ciphertext),
        "baseline_income_amount": profile.baseline_income_amount if profile else None,
        "baseline_income_frequency": profile.baseline_income_frequency if profile else None,
        "baseline_income_status": profile.baseline_income_status if profile else None,
        "income_status": profile.income_status
        or ("KNOWN" if profile.current_income_amount is not None else "NOT_RECORDED")
        if profile
        else "NOT_RECORDED",
        "baseline_employment_status": row.baseline_employment_status,
        "baseline_occupation": row.baseline_occupation,
        "baseline_captured_at": profile.baseline_captured_at if profile else None,
        "has_government_id": bool(person.government_id_ciphertext or person.voter_id_ciphertext),
        "version": row.version,
    }


def save_sensitive(
    db: Session,
    row: Participant,
    data: s.SensitiveWrite,
    principal: AuthorizationContext,
    request: Request,
    *,
    commit: bool = True,
) -> None:
    profile = db.scalar(select(SensitiveProfile).where(SensitiveProfile.participant_id == row.id))
    if profile is None:
        profile = SensitiveProfile(participant_id=row.id, created_by=staff_user_id(principal))
        db.add(profile)
    values = data.model_dump(exclude={"version"})
    values["income_status"] = data.income_status or (
        "KNOWN" if data.current_income_amount is not None else "NOT_RECORDED"
    )
    for key, value in values.items():
        if (
            key == "disability_specify"
            and value is None
            and str(data.disability_status).upper() != "YES"
        ):
            continue
        setattr(profile, key, value)
    if profile.version:
        changed(profile, staff_user_id(principal))
    changed(row, staff_user_id(principal))
    save(
        db,
        row,
        principal,
        request,
        "participant.updated",
        {"section": "sensitive", "fields": list(values)},
        commit=commit,
    )


def save_identity(
    db: Session,
    row: Participant,
    data: s.IdentityWrite,
    principal: AuthorizationContext,
    request: Request,
    *,
    commit: bool = True,
) -> None:
    raw = data.government_id.get_secret_value()
    fingerprint = identity_hash(data.government_id_type, raw)
    try:
        cipher = Fernet(settings.identity_encryption_key.get_secret_value().encode())
    except (ValueError, TypeError):
        raise ApiError(
            503,
            "IDENTITY_STORAGE_NOT_CONFIGURED",
            "An administrator must configure protected identity storage.",
        ) from None
    if db.scalar(
        select(Person.id).where(
            or_(Person.government_id_hash == fingerprint, Person.voter_id_hash == fingerprint),
            Person.id != row.person_id,
        )
    ):
        raise ApiError(
            409,
            "DUPLICATE_SUSPECTED",
            "An identity reference matches another record. Request authorized duplicate review.",
        )
    person = get_record(db, Person, row.person_id, True)
    if data.government_id_type == "VOTER_ID":
        person.voter_id_ciphertext = cipher.encrypt(raw.encode()).decode()
        person.voter_id_hash = fingerprint
    else:
        person.government_id_type = data.government_id_type
        person.government_id_ciphertext = cipher.encrypt(raw.encode()).decode()
        person.government_id_hash = fingerprint
    changed(person, staff_user_id(principal))
    changed(row, staff_user_id(principal))
    save(
        db,
        row,
        principal,
        request,
        "participant.updated",
        {"section": "identity", "fields": ["government_id"]},
        commit=commit,
    )
