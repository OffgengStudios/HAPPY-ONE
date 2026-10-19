from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select

from app.core.errors import ApiError
from app.modules.iam.dependencies import Database, Principal, authenticated, require
from app.modules.iam.service import page_query
from app.modules.marketing import schemas as data
from app.modules.marketing import service as s
from app.modules.marketing.models import Campaign, CampaignAsset, ImpactStory, MarketingRequest
from app.modules.merl.models import Outcome
from app.modules.supply.models import Consent

router = APIRouter(tags=["marketing"])
Current = Annotated[Principal, Depends(authenticated)]
RequestCreate = Annotated[Principal, Depends(require("marketing_request:create"))]
RequestRead = Annotated[Principal, Depends(require("marketing_request:view"))]
RequestEdit = Annotated[
    Principal, Depends(require("marketing_request:view", "marketing_request:edit"))
]
CampaignRead = Annotated[Principal, Depends(require("campaign:view"))]
CampaignEdit = Annotated[Principal, Depends(require("campaign:view", "campaign:edit"))]
StoryRead = Annotated[Principal, Depends(require("impact_story:view"))]
StoryEdit = Annotated[Principal, Depends(require("impact_story:view", "impact_story:edit"))]
Limit = Annotated[int, Query(ge=1, le=100)]


def visible_request(db: Database, identifier: UUID, actor: Principal) -> MarketingRequest:
    row = cast(
        MarketingRequest,
        s.get(db, MarketingRequest, identifier, "MARKETING_REQUEST_NOT_FOUND"),
    )
    if (
        "marketing_request:edit" not in actor.permissions
        and row.requesting_user_id != actor.user.id
    ):
        raise ApiError(404, "MARKETING_REQUEST_NOT_FOUND", "Record not found.")
    return row


@router.get("/marketing/dashboard")
def dashboard(db: Database, actor: CampaignRead) -> dict[str, int]:
    def count(model: type[Any], condition: Any) -> int:
        return db.scalar(select(func.count()).select_from(model).where(condition)) or 0

    return {
        "open_requests": count(
            MarketingRequest, MarketingRequest.status.not_in(["COMPLETED", "CANCELLED"])
        ),
        "in_production": count(
            Campaign, Campaign.status.in_(["DRAFT", "IN_PRODUCTION", "AWAITING_REVIEW"])
        ),
        "scheduled": count(Campaign, Campaign.status == "SCHEDULED"),
        "published": count(Campaign, Campaign.status.in_(["PUBLISHED", "COMPLETED"])),
        "consent_pending_stories": count(ImpactStory, ImpactStory.status == "CONSENT_PENDING"),
        "ready_stories": count(ImpactStory, ImpactStory.status == "READY_FOR_MARKETING"),
    }


@router.get("/marketing/requests")
def requests(
    db: Database,
    actor: RequestRead,
    status: str | None = None,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    query = select(MarketingRequest).where(MarketingRequest.archived_at.is_(None))
    if "marketing_request:edit" not in actor.permissions:
        query = query.where(MarketingRequest.requesting_user_id == actor.user.id)
    if status:
        query = query.where(MarketingRequest.status == status)
    page = page_query(query, MarketingRequest, db, limit, cursor)
    return {
        "items": [s.request_view(row) for row in page["rows"]],
        "next_cursor": page["next_cursor"],
    }


@router.post("/marketing/requests", status_code=201)
def request_create(
    values: data.RequestCreate, db: Database, actor: RequestCreate, request: Request
) -> dict[str, Any]:
    return s.request_view(s.create_request(db, values, actor, request))


@router.get("/marketing/requests/{identifier}")
def request_detail(identifier: UUID, db: Database, actor: RequestRead) -> dict[str, Any]:
    return s.request_view(visible_request(db, identifier, actor))


@router.post("/marketing/requests/{identifier}/transition")
def request_transition(
    identifier: UUID, values: data.Transition, db: Database, actor: RequestEdit, request: Request
) -> dict[str, Any]:
    row = s.get(db, MarketingRequest, identifier, "MARKETING_REQUEST_NOT_FOUND")
    return s.request_view(s.transition_request(db, row, values, actor, request))


@router.get("/campaigns")
def campaigns(
    db: Database,
    actor: CampaignRead,
    status: str | None = None,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    query = select(Campaign).where(Campaign.archived_at.is_(None))
    if status:
        query = query.where(Campaign.status == status)
    page = page_query(query, Campaign, db, limit, cursor)
    return {
        "items": [s.campaign_view(row) for row in page["rows"]],
        "next_cursor": page["next_cursor"],
    }


@router.post("/campaigns", status_code=201)
def campaign_create(
    values: data.CampaignCreate, db: Database, actor: CampaignEdit, request: Request
) -> dict[str, Any]:
    return s.campaign_view(s.create_campaign(db, values, actor, request))


@router.get("/campaigns/{identifier}")
def campaign_detail(identifier: UUID, db: Database, actor: CampaignRead) -> dict[str, Any]:
    return s.campaign_view(s.get(db, Campaign, identifier, "CAMPAIGN_NOT_FOUND"))


@router.patch("/campaigns/{identifier}")
def campaign_update(
    identifier: UUID,
    values: data.CampaignUpdate,
    db: Database,
    actor: CampaignEdit,
    request: Request,
) -> dict[str, Any]:
    row = s.get(db, Campaign, identifier, "CAMPAIGN_NOT_FOUND")
    return s.campaign_view(s.update_campaign(db, row, values, actor, request))


@router.post("/campaigns/{identifier}/transition")
def campaign_transition(
    identifier: UUID, values: data.Transition, db: Database, actor: CampaignEdit, request: Request
) -> dict[str, Any]:
    row = s.get(db, Campaign, identifier, "CAMPAIGN_NOT_FOUND")
    return s.campaign_view(s.transition_campaign(db, row, values, actor, request))


@router.post("/campaigns/{identifier}/metrics")
def campaign_metrics(
    identifier: UUID, values: data.MetricsWrite, db: Database, actor: CampaignEdit, request: Request
) -> dict[str, Any]:
    row = s.get(db, Campaign, identifier, "CAMPAIGN_NOT_FOUND")
    return s.campaign_view(s.record_metrics(db, row, values, actor, request))


@router.get("/campaigns/{identifier}/assets")
def assets(identifier: UUID, db: Database, actor: CampaignRead) -> dict[str, Any]:
    s.get(db, Campaign, identifier, "CAMPAIGN_NOT_FOUND")
    rows = db.scalars(
        select(CampaignAsset).where(
            CampaignAsset.campaign_id == identifier, CampaignAsset.archived_at.is_(None)
        )
    )
    return {"items": [s.asset_view(row) for row in rows]}


@router.post("/campaigns/{identifier}/assets", status_code=201)
def asset_create(
    identifier: UUID, values: data.AssetCreate, db: Database, actor: CampaignEdit, request: Request
) -> dict[str, Any]:
    campaign = s.get(db, Campaign, identifier, "CAMPAIGN_NOT_FOUND")
    return s.asset_view(s.create_asset(db, campaign, values, actor, request))


@router.post("/campaign-assets/{identifier}/review")
def asset_review(
    identifier: UUID, values: data.AssetReview, db: Database, actor: CampaignEdit, request: Request
) -> dict[str, Any]:
    row = s.get(db, CampaignAsset, identifier, "CAMPAIGN_ASSET_NOT_FOUND")
    return s.asset_view(s.review_asset(db, row, values, actor, request))


@router.get("/impact-stories")
def stories(
    db: Database,
    actor: StoryRead,
    status: str | None = None,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    query = select(ImpactStory).where(ImpactStory.archived_at.is_(None))
    if status:
        query = query.where(ImpactStory.status == status)
    page = page_query(query, ImpactStory, db, limit, cursor)
    return {
        "items": [s.story_view(db, row) for row in page["rows"]],
        "next_cursor": page["next_cursor"],
    }


@router.get("/impact-story-candidates")
def story_candidates(db: Database, actor: StoryRead) -> dict[str, Any]:
    existing = select(ImpactStory.source_outcome_id)
    rows = db.scalars(
        select(Outcome)
        .where(
            Outcome.archived_at.is_(None),
            Outcome.impact_story_potential.is_(True),
            Outcome.id.not_in(existing),
        )
        .order_by(Outcome.as_of_date.desc(), Outcome.created_at.desc())
        .limit(100)
    )
    return {
        "items": [
            {
                "id": row.id,
                "as_of_date": row.as_of_date,
                "currently_working": row.currently_working,
                "current_role": row.current_role,
                "progress": row.progress_text,
                "skills_gained": row.skills_gained_text,
            }
            for row in rows
        ]
    }


@router.post("/impact-stories", status_code=201)
def story_create(
    values: data.StoryCreate, db: Database, actor: StoryEdit, request: Request
) -> dict[str, Any]:
    return s.story_view(db, s.create_story(db, values, actor, request))


@router.get("/impact-stories/{identifier}")
def story_detail(identifier: UUID, db: Database, actor: StoryRead) -> dict[str, Any]:
    return s.story_view(db, s.get(db, ImpactStory, identifier, "IMPACT_STORY_NOT_FOUND"))


@router.get("/impact-stories/{identifier}/eligible-consents")
def story_consents(identifier: UUID, db: Database, actor: StoryRead) -> dict[str, Any]:
    story = s.get(db, ImpactStory, identifier, "IMPACT_STORY_NOT_FOUND")
    rows = db.scalars(
        select(Consent).where(
            Consent.participant_id == story.participant_id,
            Consent.status == "ACTIVE",
            Consent.consent_type.in_(["MARKETING", "PUBLICATION"]),
            Consent.archived_at.is_(None),
        )
    )
    return {
        "items": [
            {
                "id": row.id,
                "consent_type": row.consent_type,
                "consented_at": row.consented_at,
                "privacy_notice_version": row.privacy_notice_version,
            }
            for row in rows
        ]
    }


@router.patch("/impact-stories/{identifier}")
def story_update(
    identifier: UUID, values: data.StoryUpdate, db: Database, actor: StoryEdit, request: Request
) -> dict[str, Any]:
    row = s.get(db, ImpactStory, identifier, "IMPACT_STORY_NOT_FOUND")
    return s.story_view(db, s.update_story(db, row, values, actor, request))


@router.post("/impact-stories/{identifier}/transition")
def story_transition(
    identifier: UUID, values: data.StoryTransition, db: Database, actor: StoryEdit, request: Request
) -> dict[str, Any]:
    row = s.get(db, ImpactStory, identifier, "IMPACT_STORY_NOT_FOUND")
    return s.story_view(db, s.transition_story(db, row, values, actor, request))
