from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.modules.demand.schemas import Text, Version

Short = Annotated[str, Field(min_length=1, max_length=200)]
Code = Annotated[str, Field(min_length=1, max_length=60, pattern=r"^[A-Z][A-Z0-9_]*$")]
Priority = Literal["LOW", "NORMAL", "HIGH", "URGENT"]


class RequestCreate(BaseModel):
    request_type: Code
    vacancy_id: UUID | None = None
    training_id: UUID | None = None
    participant_id: UUID | None = None
    reason: Text
    priority: Priority = "NORMAL"
    due_at: datetime | None = None

    @model_validator(mode="after")
    def participant_scope(self) -> Self:
        if self.participant_id and self.request_type != "IMPACT_STORY":
            raise ValueError("Participant linkage is limited to impact-story requests.")
        if self.training_id and self.request_type != "TRAINING_PROMOTION":
            raise ValueError("Training linkage is limited to training-promotion requests.")
        if self.training_id and self.vacancy_id:
            raise ValueError("A request cannot link both a vacancy and training session.")
        return self


class Transition(Version):
    status: Code
    reason: Text


class CampaignWrite(BaseModel):
    title: Short
    campaign_type: Code
    owner_id: UUID | None = None
    vacancy_id: UUID | None = None
    training_id: UUID | None = None
    marketing_request_id: UUID | None = None
    audience: Text
    channels_json: list[Short] = Field(default_factory=list, max_length=30)
    planned_publish_at: datetime | None = None

    @model_validator(mode="after")
    def one_subject(self) -> Self:
        if self.training_id and self.vacancy_id:
            raise ValueError("A campaign cannot link both a vacancy and training session.")
        return self


class CampaignCreate(CampaignWrite):
    pass


class CampaignUpdate(CampaignWrite, Version):
    pass


class MetricsWrite(Version):
    metrics: dict[str, int | float | str | None]


class AssetCreate(BaseModel):
    asset_type: Code
    title: Short
    document_id: UUID | None = None
    external_url: HttpUrl | None = None
    content_text: Text | None = None
    consent_id: UUID | None = None

    @model_validator(mode="after")
    def content(self) -> Self:
        if not any((self.document_id, self.external_url, self.content_text)):
            raise ValueError("Provide a document, external URL, or content text.")
        return self


class AssetReview(Version):
    approval_status: Literal["AWAITING_REVIEW", "APPROVED", "REJECTED"]
    reason: Text


class StoryCreate(BaseModel):
    source_outcome_id: UUID
    marketing_consent_id: UUID | None = None
    owner_id: UUID | None = None


class StoryUpdate(Version):
    marketing_consent_id: UUID | None = None
    owner_id: UUID | None = None
    approved_quote: Text | None = None
    draft_text: Text | None = None


class StoryTransition(Version):
    status: Code
    reason: Text
