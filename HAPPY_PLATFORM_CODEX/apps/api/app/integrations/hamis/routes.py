from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.core.errors import ApiError
from app.integrations.hamis import service
from app.integrations.hamis.auth import HamisActor
from app.integrations.hamis.models import HamisInboundEvent
from app.integrations.hamis.schemas import EventRetry, EventReview, HamisEvent
from app.modules.iam.dependencies import Database, Principal, require
from app.modules.iam.models import now
from app.modules.iam.service import audit, page_query

router = APIRouter(tags=["hamis-integration"])
ReviewActor = Annotated[
    Principal, Depends(require("integration_event:view", "integration_event:manage"))
]
ReadActor = Annotated[Principal, Depends(require("integration_event:view"))]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.post("/integrations/hamis/events", status_code=202)
def receive_event(
    data: HamisEvent, db: Database, actor: HamisActor, request: Request
) -> dict[str, Any]:
    row, replayed = service.receive(db, data, actor, request)
    return service.event_view(row, replayed)


@router.get("/integrations/hamis/events")
def list_events(
    db: Database,
    actor: ReadActor,
    status: str | None = None,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    query = select(HamisInboundEvent)
    if status:
        query = query.where(HamisInboundEvent.status == status)
    page = page_query(query, HamisInboundEvent, db, limit, cursor)
    return {
        "items": [service.event_view(row) for row in page["rows"]],
        "next_cursor": page["next_cursor"],
    }


@router.post("/integrations/hamis/events/{identifier}/review")
def review_event(
    identifier: UUID, values: EventReview, db: Database, actor: ReviewActor, request: Request
) -> dict[str, Any]:
    row = db.get(HamisInboundEvent, identifier)
    if not row:
        raise ApiError(404, "HAMIS_EVENT_NOT_FOUND", "HAMIS event not found.")
    if row.version != values.version:
        raise ApiError(409, "RECORD_VERSION_CONFLICT", "This event changed. Refresh before saving.")
    if row.status != "NEEDS_REVIEW":
        raise ApiError(409, "HAMIS_EVENT_NOT_REVIEWABLE", "Only pending events can be reviewed.")
    row.status = "REJECTED"
    row.review_reason = values.reason
    row.reviewed_at = now()
    row.reviewed_by = actor.user.id
    row.version += 1
    audit(
        db,
        "hamis.event_rejected",
        actor.audit_actor,
        "hamis_inbound_event",
        row.id,
        request,
        changes={"reason": values.reason},
    )
    db.commit()
    return service.event_view(row)


@router.post("/integrations/hamis/events/{identifier}/retry", status_code=202)
def retry_event(
    identifier: UUID, values: EventRetry, db: Database, actor: ReviewActor, request: Request
) -> dict[str, Any]:
    row = db.get(HamisInboundEvent, identifier, with_for_update=True, populate_existing=True)
    if not row:
        raise ApiError(404, "HAMIS_EVENT_NOT_FOUND", "HAMIS event not found.")
    if row.version != values.version:
        raise ApiError(
            409, "RECORD_VERSION_CONFLICT", "This event changed. Refresh before retrying."
        )
    if row.status != "FAILED":
        raise ApiError(409, "HAMIS_EVENT_NOT_FAILED", "Only failed events can be retried.")
    row.status = "RECEIVED"
    row.attempt_count = 0
    row.error_code = None
    row.error_message = None
    row.lease_owner = None
    row.lease_expires_at = None
    row.next_attempt_at = None
    row.processed_at = None
    row.version += 1
    audit(
        db,
        "hamis.event_retried",
        actor.audit_actor,
        "hamis_inbound_event",
        row.id,
        request,
        changes={"reason": values.reason},
    )
    db.commit()
    return service.event_view(row)
