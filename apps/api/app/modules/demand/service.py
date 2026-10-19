from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.modules.demand.models import (
    Contact,
    JobDescriptionVersion,
    Organization,
    Partnership,
    PartnershipDocument,
    Record,
    Requirement,
    Vacancy,
    VacancyChange,
)
from app.modules.demand.schemas import (
    ContactFields,
    OrganizationFields,
    PartnershipFields,
    RequirementFields,
    VacancyFields,
    json_value,
    normalized_name,
)
from app.modules.iam.actors import AuthorizationContext
from app.modules.iam.dependencies import Principal
from app.modules.iam.models import AuditEvent, User, now
from app.modules.iam.service import audit, page_query, permissions_for

PARTNERSHIP_EDGES: dict[str, set[str]] = {
    "LEAD": {"CONTACTED", "DECLINED"},
    "CONTACTED": {"ENGAGED", "DECLINED"},
    "ENGAGED": {"INTERESTED", "DECLINED"},
    "INTERESTED": {"MOU_PENDING", "DECLINED"},
    "MOU_PENDING": {"MOU_SIGNED"},
    "MOU_SIGNED": {"ACTIVE"},
    "ACTIVE": {"INACTIVE"},
    "INACTIVE": {"ACTIVE"},
}
VACANCY_EDGES: dict[str, set[str]] = {
    "DRAFT": {"PENDING_CONFIRMATION", "CANCELLED"},
    "PENDING_CONFIRMATION": {"ACTIVE", "CANCELLED"},
    "ACTIVE": {"PARTIALLY_FILLED", "ON_HOLD", "CLOSED", "CANCELLED"},
    "PARTIALLY_FILLED": {"FULLY_FILLED", "ON_HOLD", "CLOSED", "CANCELLED"},
    "ON_HOLD": {"ACTIVE", "PARTIALLY_FILLED", "CLOSED", "CANCELLED"},
}
OPEN_STATES = {"ACTIVE", "PARTIALLY_FILLED", "ON_HOLD"}
PUBLIC_FIELDS: dict[type[Record], tuple[str, ...]] = {
    Organization: (*OrganizationFields.model_fields, "organization_code"),
    Contact: (*ContactFields.model_fields, "organization_id", "phone_normalized"),
    Partnership: (
        *PartnershipFields.model_fields,
        "partnership_code",
        "organization_id",
        "status",
        "owner_assigned_at",
    ),
    Vacancy: (
        *VacancyFields.model_fields,
        "organization_id",
        "vacancy_code",
        "status",
        "opened_at",
        "closed_at",
        "closure_reason",
        "closure_note",
    ),
    Requirement: (*RequirementFields.model_fields, "vacancy_id"),
    PartnershipDocument: (
        "partnership_id",
        "document_code",
        "original_filename",
        "mime_type",
        "size_bytes",
        "version_number",
        "scan_status",
        "scan_details",
    ),
    JobDescriptionVersion: (
        "vacancy_id",
        "document_code",
        "original_filename",
        "mime_type",
        "size_bytes",
        "version_number",
        "scan_status",
        "scan_details",
    ),
}


def fail(code: str, message: str, status: int = 409) -> None:
    raise ApiError(status, code, message)


def get_record[T: Record](db: Session, model: type[T], identifier: UUID, lock: bool = False) -> T:
    # Demand mutations lock the employer before its vacancy to serialize archiving.
    if lock and model is Vacancy:
        employer_id = db.scalar(select(Vacancy.organization_id).where(Vacancy.id == identifier))
        if employer_id:
            organization_exists(db, employer_id, True)
    query = select(model).where(model.id == identifier)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise ApiError(404, "RECORD_NOT_FOUND", "This record does not exist.")
    return row


def writable(row: Record, version: int) -> None:
    if row.archived_at:
        fail("RECORD_ARCHIVED", "Archived records cannot be changed.")
    if row.version != version:
        fail("RECORD_VERSION_CONFLICT", "This record changed. Refresh before saving.")


def changed(row: Record, actor: UUID) -> None:
    row.version += 1
    row.updated_by = actor
    row.updated_at = now()


def assignable(db: Session, identifier: UUID | None, permission: str) -> None:
    if identifier is None:
        return
    user = db.get(User, identifier)
    if not user or not user.is_active or permission not in permissions_for(user):
        fail("INVALID_OWNER", "Choose an active staff member with the required access.", 422)


def organization_exists(db: Session, identifier: UUID, lock: bool = False) -> Organization:
    row = get_record(db, Organization, identifier, lock)
    if row.archived_at:
        fail("RECORD_ARCHIVED", "The employer is archived.")
    return row


def duplicate_check(db: Session, name: str, identifier: UUID | None, acknowledged: bool) -> None:
    query = select(Organization.id).where(
        Organization.normalized_name == normalized_name(name), Organization.archived_at.is_(None)
    )
    if identifier:
        query = query.where(Organization.id != identifier)
    if db.scalar(query) and not acknowledged:
        fail(
            "POSSIBLE_DUPLICATE",
            "An employer with this name exists. Review it or acknowledge a distinct employer.",
        )


def view(row: Record) -> dict[str, Any]:
    fields = PUBLIC_FIELDS[type(row)] + (
        "id",
        "version",
        "created_at",
        "updated_at",
        "archived_at",
        "source_system",
        "created_via",
    )
    return {key: json_value(getattr(row, key)) for key in fields}


def organization_view(db: Session, row: Organization) -> dict[str, Any]:
    partnership = db.scalar(
        select(Partnership)
        .where(Partnership.organization_id == row.id, Partnership.archived_at.is_(None))
        .order_by(Partnership.start_date.desc(), Partnership.created_at.desc())
        .limit(1)
    )
    return {**view(row), "status": partnership.status if partnership else "LEAD"}


def partnership_view(row: Partnership) -> dict[str, Any]:
    allowed = PARTNERSHIP_EDGES.get(row.status, set()).copy()
    if row.status == "INTERESTED" and not row.mou_required:
        allowed.add("ACTIVE")
    return {**view(row), "allowed_transitions": sorted(allowed)}


def headcount(row: Vacancy, db: Session | None = None) -> dict[str, int]:
    started, confirmed = 0, 0
    if db is not None:
        from app.modules.placement.models import Placement

        started = (
            db.scalar(
                select(func.count())
                .select_from(Placement)
                .where(
                    Placement.vacancy_id == row.id,
                    Placement.actual_start_date.is_not(None),
                    Placement.status.not_in({"FAILED_TO_START", "CANCELLED"}),
                    Placement.archived_at.is_(None),
                )
            )
            or 0
        )
        confirmed = (
            db.scalar(
                select(func.count())
                .select_from(Placement)
                .where(
                    Placement.vacancy_id == row.id,
                    Placement.confirmed_at.is_not(None),
                    Placement.archived_at.is_(None),
                )
            )
            or 0
        )
    return {
        "required": row.required_headcount,
        "started": started,
        "confirmed_placements": confirmed,
        "outstanding": max(row.required_headcount - started, 0),
    }


def vacancy_view(db: Session, row: Vacancy) -> dict[str, Any]:
    from app.core.config import settings

    employer = get_record(db, Organization, row.organization_id)
    end = row.closed_at or now()
    age = max((end.date() - row.opened_at.date()).days, 0) if row.opened_at else None
    allowed = VACANCY_EDGES.get(row.status, set()).copy()
    if row.status == "DRAFT" and not settings.demand_vacancy_confirmation_required:
        allowed.add("ACTIVE")
    return {
        **view(row),
        "organization_name": employer.name,
        "headcount": headcount(row, db),
        "age_days": age,
        "allowed_transitions": sorted(allowed),
    }


def log_change(
    db: Session, vacancy: Vacancy, field: str, old: Any, new: Any, reason: str | None, actor: UUID
) -> None:
    db.add(
        VacancyChange(
            vacancy_id=vacancy.id,
            field_name=field,
            old_value_json=json_value(old),
            new_value_json=json_value(new),
            reason=reason,
            changed_by=actor,
        )
    )


def persist(
    db: Session,
    principal: Principal,
    request: Request,
    row: Record,
    code: str,
    fields: list[str] | None = None,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db.flush()
    audit(
        db,
        code,
        principal.user.id,
        row.__tablename__,  # type: ignore[attr-defined]
        row.id,
        request,
        changes={"fields": fields or [], "reason": reason, **(details or {})},
    )
    db.commit()


def create_organization(
    db: Session, data: dict[str, Any], principal: Principal, request: Request
) -> Organization:
    acknowledged = data.pop("duplicate_acknowledged")
    required = data.pop("mou_required")
    duplicate_check(db, data["name"], None, acknowledged)
    assignable(db, data["relationship_owner_id"], "workspace_demand:view")
    row = Organization(
        **data,
        organization_code="EMP-" + uuid4().hex[:12].upper(),
        normalized_name=normalized_name(data["name"]),
        created_by=principal.user.id,
    )
    db.add(row)
    db.flush()
    db.add(
        Partnership(
            partnership_code="PAR-" + uuid4().hex[:12].upper(),
            organization_id=row.id,
            partnership_type="RECRUITMENT",
            start_date=now().date(),
            mou_required=required,
            owner_id=row.relationship_owner_id,
            owner_assigned_at=now() if row.relationship_owner_id else None,
            created_by=principal.user.id,
        )
    )
    persist(db, principal, request, row, "organization.created", details={"mou_required": required})
    return row


def contact_primary(db: Session, row: Contact) -> None:
    if row.is_primary and row.is_active:
        other = db.scalar(
            select(Contact.id).where(
                Contact.organization_id == row.organization_id,
                Contact.id != row.id,
                Contact.is_primary.is_(True),
                Contact.is_active.is_(True),
                Contact.archived_at.is_(None),
            )
        )
        if other:
            fail(
                "PRIMARY_CONTACT_EXISTS",
                "Deactivate the existing primary contact before assigning another.",
            )


def partnership_transition(row: Partnership, target: str, reason: str | None) -> None:
    allowed = PARTNERSHIP_EDGES.get(row.status, set()).copy()
    if row.status == "INTERESTED" and not row.mou_required:
        allowed.add("ACTIVE")
    if target not in allowed:
        fail(
            "INVALID_STATUS_TRANSITION",
            "This employer relationship transition is not allowed.",
            422,
        )
    if not row.mou_signed_at and (
        target == "MOU_SIGNED" or (target == "ACTIVE" and row.mou_required)
    ):
        fail("MOU_SIGNATURE_REQUIRED", "Record the MOU signed date before this transition.")
    if row.status == "INACTIVE" and not reason:
        fail("TRANSITION_REASON_REQUIRED", "Reactivation needs a reason.", 422)
    row.status = target


def vacancy_transition(
    row: Vacancy,
    target: str,
    confirmation_required: bool,
    closure_reason: str | None,
    closure_note: str | None,
    db: Session | None = None,
) -> None:
    allowed = VACANCY_EDGES.get(row.status, set()).copy()
    if row.status == "DRAFT" and not confirmation_required:
        allowed.add("ACTIVE")
    if target not in allowed:
        fail("INVALID_STATUS_TRANSITION", "This vacancy transition is not allowed.", 422)
    if target in {"CLOSED", "CANCELLED"} and not closure_reason:
        fail("CLOSURE_REASON_REQUIRED", "Closing or cancelling needs a reason.", 422)
    counts = headcount(row, db)
    if target == "PARTIALLY_FILLED" and not 0 < counts["started"] < counts["required"]:
        fail(
            "HEADCOUNT_STATE_MISMATCH",
            "Partial fill needs recorded actual starts below the required headcount.",
        )
    if target == "FULLY_FILLED" and counts["started"] < counts["required"]:
        fail("HEADCOUNT_STATE_MISMATCH", "Full fill needs sufficient recorded actual starts.")
    if target == "ACTIVE" and not row.opened_at:
        row.opened_at = now()
    if target in {"CLOSED", "CANCELLED"}:
        row.closed_at, row.closure_reason, row.closure_note = now(), closure_reason, closure_note
    row.status = target


def activity(
    db: Session,
    entity: str,
    identifier: UUID,
    limit: int,
    cursor: str | None,
    actor: AuthorizationContext,
) -> dict[str, Any]:
    filters = [
        and_(
            AuditEvent.entity_type == entity,
            AuditEvent.entity_id == identifier,
        )
    ]
    if entity == "organizations":
        # Apply child-resource permissions in SQL, before pagination or serialization.
        if "partnership:view" in actor.permissions:
            filters.append(
                and_(
                    AuditEvent.entity_type == "partnerships",
                    AuditEvent.entity_id.in_(
                        select(Partnership.id).where(Partnership.organization_id == identifier)
                    ),
                )
            )
        if "organization_contact:view" in actor.permissions:
            filters.append(
                and_(
                    AuditEvent.entity_type == "organization_contacts",
                    AuditEvent.entity_id.in_(
                        select(Contact.id).where(Contact.organization_id == identifier)
                    ),
                )
            )
    query = select(AuditEvent).where(or_(*filters))
    page = page_query(query, AuditEvent, db, limit, cursor)
    return {
        "items": [
            {
                "id": str(row.id),
                "event_code": row.event_code,
                "occurred_at": row.occurred_at.isoformat(),
                "actor_type": row.actor_type,
                "actor_id": json_value(row.actor_id),
                "changes": row.after_json,
            }
            for row in page["rows"]
        ],
        "next_cursor": page["next_cursor"],
    }


def work_bucket(due: datetime | None) -> str:
    today = datetime.now(UTC).date()
    if not due:
        return "Upcoming"
    if due.date() < today:
        return "Overdue"
    return "Due today" if due.date() == today else "Upcoming"
