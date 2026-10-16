from typing import Any, NoReturn, cast
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.modules.demand.models import Vacancy
from app.modules.demand.service import assignable, changed, writable
from app.modules.iam.dependencies import Principal
from app.modules.iam.models import now
from app.modules.iam.service import audit
from app.modules.marketing import schemas as data
from app.modules.marketing.models import Campaign, CampaignAsset, ImpactStory, MarketingRequest
from app.modules.merl.models import Outcome
from app.modules.supply.models import Consent, Document, Participant, Person
from app.modules.training.models import Training


def fail(code: str, message: str, status: int = 409) -> NoReturn:
    raise ApiError(status, code, message)


def primary_workstream(actor: Principal) -> str:
    role = next((row for row in actor.user.roles if row.id == actor.user.primary_role_id), None)
    return role.code if role else "UNASSIGNED"


def get(db: Session, model: type[Any], identifier: UUID, code: str) -> Any:
    row = db.get(model, identifier)
    if not row or getattr(row, "archived_at", None):
        fail(code, "Record not found.", 404)
    return row


def request_view(row: MarketingRequest) -> dict[str, Any]:
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "version",
            "request_code",
            "requesting_workstream",
            "requesting_user_id",
            "request_type",
            "vacancy_id",
            "training_id",
            "participant_id",
            "reason",
            "priority",
            "status",
            "due_at",
            "owner_id",
            "created_at",
            "updated_at",
        )
    }


def create_request(
    db: Session, values: data.RequestCreate, actor: Principal, request: Request
) -> MarketingRequest:
    if values.vacancy_id:
        get(db, Vacancy, values.vacancy_id, "VACANCY_NOT_FOUND")
    if values.training_id:
        if "training:view" not in actor.permissions:
            fail("PERMISSION_DENIED", "Training linkage is not permitted.", 403)
        get(db, Training, values.training_id, "TRAINING_NOT_FOUND")
    if values.participant_id:
        if "participant:view" not in actor.permissions:
            fail("PERMISSION_DENIED", "Participant linkage is not permitted.", 403)
        get(db, Participant, values.participant_id, "PARTICIPANT_NOT_FOUND")
    row = MarketingRequest(
        request_code="MREQ-" + uuid4().hex.upper(),
        requesting_workstream=primary_workstream(actor),
        requesting_user_id=actor.user.id,
        created_by=actor.user.id,
        updated_by=actor.user.id,
        **values.model_dump(),
    )
    db.add(row)
    db.flush()
    audit(db, "marketing_request.created", actor.audit_actor, "marketing_request", row.id, request)
    db.commit()
    return row


REQUEST_TRANSITIONS = {
    "REQUESTED": {"ACCEPTED", "CANCELLED"},
    "ACCEPTED": {"IN_PRODUCTION", "CANCELLED"},
    "IN_PRODUCTION": {"AWAITING_REVIEW", "CANCELLED"},
    "AWAITING_REVIEW": {"IN_PRODUCTION", "APPROVED", "CANCELLED"},
    "APPROVED": {"PUBLISHED", "COMPLETED", "CANCELLED"},
    "PUBLISHED": {"COMPLETED"},
}


def transition_request(
    db: Session, row: MarketingRequest, values: data.Transition, actor: Principal, request: Request
) -> MarketingRequest:
    writable(row, values.version)
    if values.status not in REQUEST_TRANSITIONS.get(row.status, set()):
        fail("INVALID_MARKETING_REQUEST_TRANSITION", "That request transition is not allowed.")
    before = row.status
    row.status = values.status
    changed(row, actor.user.id)
    audit(
        db,
        "marketing_request.status_changed",
        actor.audit_actor,
        "marketing_request",
        row.id,
        request,
        changes={"from": before, "to": row.status, "reason": values.reason},
    )
    db.commit()
    return row


def campaign_view(row: Campaign) -> dict[str, Any]:
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "version",
            "campaign_code",
            "title",
            "campaign_type",
            "status",
            "owner_id",
            "vacancy_id",
            "training_id",
            "marketing_request_id",
            "audience",
            "channels_json",
            "planned_publish_at",
            "published_at",
            "metrics_json",
            "created_at",
            "updated_at",
        )
    }


def validate_campaign_links(db: Session, values: data.CampaignWrite) -> None:
    if values.vacancy_id:
        get(db, Vacancy, values.vacancy_id, "VACANCY_NOT_FOUND")
    if values.training_id:
        get(db, Training, values.training_id, "TRAINING_NOT_FOUND")
    if values.marketing_request_id:
        request_row = get(
            db, MarketingRequest, values.marketing_request_id, "MARKETING_REQUEST_NOT_FOUND"
        )
        if request_row.vacancy_id and request_row.vacancy_id != values.vacancy_id:
            fail(
                "CAMPAIGN_REQUEST_LINEAGE_MISMATCH",
                "Campaign vacancy must match its source request.",
                422,
            )
        if request_row.training_id and request_row.training_id != values.training_id:
            fail(
                "CAMPAIGN_REQUEST_LINEAGE_MISMATCH",
                "Campaign training must match its source request.",
                422,
            )
    assignable(db, values.owner_id, "campaign:edit")


def create_campaign(
    db: Session, values: data.CampaignCreate, actor: Principal, request: Request
) -> Campaign:
    validate_campaign_links(db, values)
    row = Campaign(
        campaign_code="CMP-" + uuid4().hex.upper(),
        created_by=actor.user.id,
        updated_by=actor.user.id,
        **values.model_dump(),
    )
    db.add(row)
    db.flush()
    audit(db, "campaign.created", actor.audit_actor, "campaign", row.id, request)
    db.commit()
    return row


def update_campaign(
    db: Session, row: Campaign, values: data.CampaignUpdate, actor: Principal, request: Request
) -> Campaign:
    writable(row, values.version)
    validate_campaign_links(db, values)
    if row.status in {"PUBLISHED", "COMPLETED", "CANCELLED"}:
        fail("CAMPAIGN_CLOSED", "Published or closed campaigns cannot be edited.")
    for key, value in values.model_dump(exclude={"version"}).items():
        setattr(row, key, value)
    changed(row, actor.user.id)
    audit(db, "campaign.updated", actor.audit_actor, "campaign", row.id, request)
    db.commit()
    return row


CAMPAIGN_TRANSITIONS = {
    "DRAFT": {"IN_PRODUCTION", "CANCELLED"},
    "IN_PRODUCTION": {"AWAITING_REVIEW", "CANCELLED"},
    "AWAITING_REVIEW": {"IN_PRODUCTION", "APPROVED", "CANCELLED"},
    "APPROVED": {"SCHEDULED", "PUBLISHED", "CANCELLED"},
    "SCHEDULED": {"APPROVED", "PUBLISHED", "CANCELLED"},
    "PUBLISHED": {"COMPLETED"},
}


def transition_campaign(
    db: Session, row: Campaign, values: data.Transition, actor: Principal, request: Request
) -> Campaign:
    writable(row, values.version)
    if values.status not in CAMPAIGN_TRANSITIONS.get(row.status, set()):
        fail("INVALID_CAMPAIGN_TRANSITION", "That campaign transition is not allowed.")
    if values.status == "SCHEDULED" and not row.planned_publish_at:
        fail("CAMPAIGN_SCHEDULE_REQUIRED", "Set a planned publication time first.", 422)
    before = row.status
    row.status = values.status
    if values.status == "PUBLISHED":
        row.published_at = now()
    changed(row, actor.user.id)
    audit(
        db,
        "campaign.status_changed",
        actor.audit_actor,
        "campaign",
        row.id,
        request,
        changes={"from": before, "to": row.status, "reason": values.reason},
    )
    db.commit()
    return row


def record_metrics(
    db: Session, row: Campaign, values: data.MetricsWrite, actor: Principal, request: Request
) -> Campaign:
    writable(row, values.version)
    if row.status not in {"PUBLISHED", "COMPLETED"}:
        fail("CAMPAIGN_NOT_PUBLISHED", "Metrics require a published campaign.")
    row.metrics_json = {**row.metrics_json, **values.metrics}
    changed(row, actor.user.id)
    audit(
        db,
        "campaign.metrics_recorded",
        actor.audit_actor,
        "campaign",
        row.id,
        request,
        changes={"metric_keys": sorted(values.metrics)},
    )
    db.commit()
    return row


def asset_view(row: CampaignAsset) -> dict[str, Any]:
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "version",
            "campaign_id",
            "asset_type",
            "title",
            "document_id",
            "external_url",
            "content_text",
            "approval_status",
            "consent_id",
            "created_at",
            "updated_at",
        )
    }


def create_asset(
    db: Session, campaign: Campaign, values: data.AssetCreate, actor: Principal, request: Request
) -> CampaignAsset:
    if values.document_id:
        document = get(db, Document, values.document_id, "DOCUMENT_NOT_FOUND")
        if document.document_type == "CV":
            fail(
                "INVALID_CAMPAIGN_ASSET",
                "Participant CVs cannot be used as campaign assets.",
                422,
            )
    if values.consent_id:
        validate_consent(db, values.consent_id)
    row = CampaignAsset(
        campaign_id=campaign.id,
        created_by=actor.user.id,
        updated_by=actor.user.id,
        **values.model_dump(mode="json", exclude={"external_url"}),
        external_url=str(values.external_url) if values.external_url else None,
    )
    db.add(row)
    db.flush()
    audit(db, "campaign_asset.created", actor.audit_actor, "campaign_asset", row.id, request)
    db.commit()
    return row


def validate_consent(db: Session, identifier: UUID, participant_id: UUID | None = None) -> Consent:
    consent = cast(Consent, get(db, Consent, identifier, "MARKETING_CONSENT_NOT_FOUND"))
    if (
        consent.status != "ACTIVE"
        or consent.consent_type not in {"MARKETING", "PUBLICATION"}
        or (participant_id and consent.participant_id != participant_id)
    ):
        fail("MARKETING_CONSENT_REQUIRED", "Active marketing/publication consent is required.", 422)
    return consent


def review_asset(
    db: Session, row: CampaignAsset, values: data.AssetReview, actor: Principal, request: Request
) -> CampaignAsset:
    writable(row, values.version)
    if values.approval_status == "APPROVED" and row.document_id:
        document = get(db, Document, row.document_id, "DOCUMENT_NOT_FOUND")
        if not row.consent_id:
            fail("MARKETING_CONSENT_REQUIRED", "Participant assets require consent.", 422)
        validate_consent(db, row.consent_id, document.participant_id)
    row.approval_status = values.approval_status
    changed(row, actor.user.id)
    audit(
        db,
        "campaign_asset.reviewed",
        actor.audit_actor,
        "campaign_asset",
        row.id,
        request,
        changes={"status": row.approval_status, "reason": values.reason},
    )
    db.commit()
    return row


def story_view(db: Session, row: ImpactStory) -> dict[str, Any]:
    outcome = get(db, Outcome, row.source_outcome_id, "OUTCOME_NOT_FOUND")
    participant = get(db, Participant, row.participant_id, "PARTICIPANT_NOT_FOUND")
    person = get(db, Person, participant.person_id, "PERSON_NOT_FOUND")
    consent = db.get(Consent, row.marketing_consent_id) if row.marketing_consent_id else None
    can_identify = bool(
        consent
        and consent.participant_id == row.participant_id
        and consent.status == "ACTIVE"
        and consent.consent_type in {"MARKETING", "PUBLICATION"}
    )
    return {
        **{
            key: getattr(row, key)
            for key in (
                "id",
                "version",
                "story_code",
                "participant_id",
                "source_outcome_id",
                "marketing_consent_id",
                "status",
                "owner_id",
                "approved_quote",
                "draft_text",
                "approved_at",
                "published_at",
                "created_at",
                "updated_at",
            )
        },
        "participant_name": (
            " ".join(filter(None, [person.first_name, person.other_names, person.surname]))
            if can_identify
            else None
        ),
        "approved_facts": {
            "as_of_date": outcome.as_of_date,
            "currently_working": outcome.currently_working,
            "current_role": outcome.current_role,
            "skills_gained": outcome.skills_gained_text,
            "progress": outcome.progress_text,
        },
    }


def create_story(
    db: Session, values: data.StoryCreate, actor: Principal, request: Request
) -> ImpactStory:
    outcome = get(db, Outcome, values.source_outcome_id, "OUTCOME_NOT_FOUND")
    if not outcome.impact_story_potential:
        fail("OUTCOME_NOT_STORY_CANDIDATE", "M&E must identify the outcome first.", 422)
    if db.scalar(select(ImpactStory.id).where(ImpactStory.source_outcome_id == outcome.id)):
        fail("IMPACT_STORY_EXISTS", "This outcome already has an impact story.")
    if values.marketing_consent_id:
        validate_consent(db, values.marketing_consent_id, outcome.participant_id)
    assignable(db, values.owner_id, "impact_story:edit")
    row = ImpactStory(
        story_code="STORY-" + uuid4().hex.upper(),
        participant_id=outcome.participant_id,
        source_outcome_id=outcome.id,
        status="IDENTIFIED",
        created_by=actor.user.id,
        updated_by=actor.user.id,
        marketing_consent_id=values.marketing_consent_id,
        owner_id=values.owner_id,
    )
    db.add(row)
    db.flush()
    audit(db, "impact_story.created", actor.audit_actor, "impact_story", row.id, request)
    db.commit()
    return row


def update_story(
    db: Session, row: ImpactStory, values: data.StoryUpdate, actor: Principal, request: Request
) -> ImpactStory:
    writable(row, values.version)
    if values.marketing_consent_id:
        validate_consent(db, values.marketing_consent_id, row.participant_id)
    assignable(db, values.owner_id, "impact_story:edit")
    for key, value in values.model_dump(exclude={"version"}).items():
        setattr(row, key, value)
    changed(row, actor.user.id)
    audit(db, "impact_story.updated", actor.audit_actor, "impact_story", row.id, request)
    db.commit()
    return row


STORY_TRANSITIONS = {
    "IDENTIFIED": {"CONSENT_PENDING", "READY_FOR_MARKETING", "REJECTED", "CANCELLED"},
    "CONSENT_PENDING": {"READY_FOR_MARKETING", "REJECTED", "CANCELLED"},
    "READY_FOR_MARKETING": {"DRAFTING", "CANCELLED"},
    "DRAFTING": {"REVIEW", "CANCELLED"},
    "REVIEW": {"DRAFTING", "APPROVED", "REJECTED", "CANCELLED"},
    "APPROVED": {"PUBLISHED", "DRAFTING", "CANCELLED"},
}


def transition_story(
    db: Session, row: ImpactStory, values: data.StoryTransition, actor: Principal, request: Request
) -> ImpactStory:
    writable(row, values.version)
    if values.status not in STORY_TRANSITIONS.get(row.status, set()):
        fail("INVALID_IMPACT_STORY_TRANSITION", "That story transition is not allowed.")
    if values.status in {"READY_FOR_MARKETING", "DRAFTING", "REVIEW", "APPROVED", "PUBLISHED"}:
        if not row.marketing_consent_id:
            fail(
                "MARKETING_CONSENT_REQUIRED",
                "Active marketing/publication consent is required.",
                422,
            )
        validate_consent(db, row.marketing_consent_id, row.participant_id)
    if values.status == "APPROVED" and not row.draft_text:
        fail("IMPACT_STORY_DRAFT_REQUIRED", "A draft is required before approval.", 422)
    before = row.status
    row.status = values.status
    if values.status == "APPROVED":
        row.approved_at = now()
    if values.status == "PUBLISHED":
        row.published_at = now()
    changed(row, actor.user.id)
    audit(
        db,
        "impact_story.status_changed",
        actor.audit_actor,
        "impact_story",
        row.id,
        request,
        changes={"from": before, "to": row.status, "reason": values.reason},
    )
    db.commit()
    return row
