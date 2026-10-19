from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.modules.demand.models import Organization, Record, Vacancy
from app.modules.demand.service import get_record
from app.modules.external_references.models import ExternalReference
from app.modules.external_references.schemas import ReferenceCreate, ReferencePatch
from app.modules.iam.actors import AuthorizationContext
from app.modules.iam.models import now
from app.modules.iam.service import audit
from app.modules.supply.models import Participant

ENTITIES: dict[str, tuple[type[Record], str]] = {
    "PARTICIPANT": (Participant, "participant"),
    "ORGANIZATION": (Organization, "organization"),
    "VACANCY": (Vacancy, "vacancy"),
}


def authorize_entity(
    db: Session,
    actor: AuthorizationContext,
    entity_type: str,
    identifier: UUID,
    write: bool = False,
) -> Record:
    mapping = ENTITIES.get(entity_type)
    if mapping is None:
        raise ApiError(422, "UNSUPPORTED_ENTITY_TYPE", "This entity type is not supported.")
    model, resource = mapping
    required = {"external_reference:view", f"{resource}:view"}
    if write:
        required |= {"external_reference:manage", f"{resource}:edit"}
    if not required <= actor.permissions:
        raise ApiError(
            403, "PERMISSION_DENIED", "You do not have permission for this record's references."
        )
    row = get_record(db, model, identifier, write)
    if write and row.archived_at:
        raise ApiError(409, "RECORD_ARCHIVED", "Archived records cannot receive reference changes.")
    return row


def view(row: ExternalReference) -> dict[str, Any]:
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "entity_type",
            "entity_id",
            "external_system",
            "external_id",
            "external_metadata",
            "created_at",
            "updated_at",
            "version",
        )
    }


def create(
    db: Session, data: ReferenceCreate, actor: AuthorizationContext, request: Request | None = None
) -> ExternalReference:
    authorize_entity(db, actor, data.entity_type, data.entity_id, True)
    # Metadata is inert; never use it for grants, scopes, provenance, or domain updates.
    row = ExternalReference(**data.model_dump())
    db.add(row)
    db.flush()
    audit(
        db,
        "external_reference.created",
        actor.audit_actor,
        data.entity_type.lower(),
        data.entity_id,
        request,
        changes={"reference_id": str(row.id), "external_system": row.external_system},
    )
    db.commit()
    return row


def get(db: Session, identifier: UUID) -> ExternalReference:
    row = db.get(ExternalReference, identifier)
    if row is None:
        raise ApiError(404, "REFERENCE_NOT_FOUND", "This external reference does not exist.")
    return row


def update(
    db: Session,
    row: ExternalReference,
    data: ReferencePatch,
    actor: AuthorizationContext,
    request: Request | None = None,
) -> ExternalReference:
    authorize_entity(db, actor, row.entity_type, row.entity_id, True)
    current = db.scalar(
        select(ExternalReference)
        .where(ExternalReference.id == row.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if current is None:
        raise ApiError(404, "REFERENCE_NOT_FOUND", "This external reference does not exist.")
    if current.version != data.version:
        raise ApiError(
            409, "RECORD_VERSION_CONFLICT", "This reference changed. Refresh before saving."
        )
    current.external_metadata = data.external_metadata
    current.version += 1
    current.updated_at = now()
    audit(
        db,
        "external_reference.updated",
        actor.audit_actor,
        current.entity_type.lower(),
        current.entity_id,
        request,
        changes={"reference_id": str(current.id), "fields": ["external_metadata"]},
    )
    db.commit()
    return current
