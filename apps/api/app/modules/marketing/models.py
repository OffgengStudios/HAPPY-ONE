from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.modules.demand.models import Record


class MarketingRequest(Record, Base):
    __tablename__ = "marketing_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('REQUESTED','ACCEPTED','IN_PRODUCTION','AWAITING_REVIEW',"
            "'APPROVED','PUBLISHED','COMPLETED','CANCELLED')",
            name="ck_marketing_request_status",
        ),
        CheckConstraint(
            "priority IN ('LOW','NORMAL','HIGH','URGENT')",
            name="ck_marketing_request_priority",
        ),
        Index("ix_marketing_request_status_due", "status", "due_at"),
    )
    request_code: Mapped[str] = mapped_column(String(40), unique=True)
    requesting_workstream: Mapped[str] = mapped_column(String(40), index=True)
    requesting_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    request_type: Mapped[str] = mapped_column(String(60))
    vacancy_id: Mapped[UUID | None] = mapped_column(ForeignKey("vacancies.id"), index=True)
    training_id: Mapped[UUID | None] = mapped_column(ForeignKey("trainings.id"), index=True)
    participant_id: Mapped[UUID | None] = mapped_column(ForeignKey("participants.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(15), default="NORMAL")
    status: Mapped[str] = mapped_column(String(30), default="REQUESTED", index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)


class Campaign(Record, Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','IN_PRODUCTION','AWAITING_REVIEW','APPROVED',"
            "'SCHEDULED','PUBLISHED','COMPLETED','CANCELLED')",
            name="ck_campaign_status",
        ),
        CheckConstraint(
            "status <> 'SCHEDULED' OR planned_publish_at IS NOT NULL",
            name="ck_campaign_schedule",
        ),
        CheckConstraint(
            "status NOT IN ('PUBLISHED','COMPLETED') OR published_at IS NOT NULL",
            name="ck_campaign_publication",
        ),
    )
    campaign_code: Mapped[str] = mapped_column(String(40), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    campaign_type: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)
    owner_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    vacancy_id: Mapped[UUID | None] = mapped_column(ForeignKey("vacancies.id"), index=True)
    training_id: Mapped[UUID | None] = mapped_column(ForeignKey("trainings.id"), index=True)
    marketing_request_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("marketing_requests.id"), index=True
    )
    audience: Mapped[str] = mapped_column(Text)
    channels_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    planned_publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class CampaignAsset(Record, Base):
    __tablename__ = "campaign_assets"
    __table_args__ = (
        CheckConstraint(
            "approval_status IN ('DRAFT','AWAITING_REVIEW','APPROVED','REJECTED')",
            name="ck_campaign_asset_approval",
        ),
        CheckConstraint(
            "document_id IS NOT NULL OR external_url IS NOT NULL OR content_text IS NOT NULL",
            name="ck_campaign_asset_content",
        ),
    )
    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("campaigns.id"), index=True)
    asset_type: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200))
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"))
    external_url: Mapped[str | None] = mapped_column(String(1000))
    content_text: Mapped[str | None] = mapped_column(Text)
    approval_status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    consent_id: Mapped[UUID | None] = mapped_column(ForeignKey("consents.id"))


class ImpactStory(Record, Base):
    __tablename__ = "impact_stories"
    __table_args__ = (
        CheckConstraint(
            "status IN ('IDENTIFIED','CONSENT_PENDING','READY_FOR_MARKETING','DRAFTING',"
            "'REVIEW','APPROVED','PUBLISHED','REJECTED','CANCELLED')",
            name="ck_impact_story_status",
        ),
        CheckConstraint(
            "status <> 'READY_FOR_MARKETING' OR marketing_consent_id IS NOT NULL",
            name="ck_impact_story_ready_consent",
        ),
        CheckConstraint(
            "status <> 'PUBLISHED' OR published_at IS NOT NULL",
            name="ck_impact_story_publication",
        ),
    )
    story_code: Mapped[str] = mapped_column(String(40), unique=True)
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("participants.id"), index=True)
    source_outcome_id: Mapped[UUID] = mapped_column(ForeignKey("outcomes.id"), unique=True)
    marketing_consent_id: Mapped[UUID | None] = mapped_column(ForeignKey("consents.id"))
    status: Mapped[str] = mapped_column(String(30), default="IDENTIFIED", index=True)
    owner_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    approved_quote: Mapped[str | None] = mapped_column(Text)
    draft_text: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
