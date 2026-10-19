from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select

from app.modules.external_references import service
from app.modules.external_references.models import ExternalReference
from app.modules.external_references.schemas import EntityType, ReferenceCreate, ReferencePatch
from app.modules.iam.dependencies import Database, Principal, require
from app.modules.iam.service import page_query

router = APIRouter(prefix="/external-references", tags=["external-references"])
Read = Annotated[Principal, Depends(require("external_reference:view"))]
Manage = Annotated[
    Principal, Depends(require("external_reference:view", "external_reference:manage"))
]


@router.get("")
def references(
    entity_type: EntityType,
    entity_id: UUID,
    db: Database,
    actor: Read,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    service.authorize_entity(db, actor, entity_type, entity_id)
    response.headers["Cache-Control"] = "no-store"
    query = select(ExternalReference).where(
        ExternalReference.entity_type == entity_type, ExternalReference.entity_id == entity_id
    )
    page = page_query(query, ExternalReference, db, limit, cursor)
    return {
        "items": [service.view(row) for row in page["rows"]],
        "next_cursor": page["next_cursor"],
    }


@router.get("/{identifier}")
def detail(identifier: UUID, db: Database, actor: Read, response: Response) -> dict[str, Any]:
    row = service.get(db, identifier)
    service.authorize_entity(db, actor, row.entity_type, row.entity_id)
    response.headers["Cache-Control"] = "no-store"
    return service.view(row)


@router.post("", status_code=201)
def create(
    data: ReferenceCreate, db: Database, actor: Manage, request: Request, response: Response
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return service.view(service.create(db, data, actor, request))


@router.patch("/{identifier}")
def update(
    identifier: UUID,
    data: ReferencePatch,
    db: Database,
    actor: Manage,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return service.view(service.update(db, service.get(db, identifier), data, actor, request))
