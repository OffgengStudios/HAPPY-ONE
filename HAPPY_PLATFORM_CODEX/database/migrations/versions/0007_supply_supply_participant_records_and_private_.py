"""Supply participant records and private CV versions

Revision ID: 0007_supply
Revises: 0006_mou_signed_date
Create Date: 2026-10-07 07:28:30.201062
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_supply"
down_revision: str | None = "0006_mou_signed_date"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "people",
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("surname", sa.String(length=100), nullable=False),
        sa.Column("other_names", sa.String(length=100), nullable=True),
        sa.Column("normalized_name", sa.String(length=310), nullable=False),
        sa.Column("phone_raw", sa.String(length=50), nullable=False),
        sa.Column("phone_normalized", sa.String(length=30), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("region_code", sa.String(length=60), nullable=True),
        sa.Column("district_code", sa.String(length=60), nullable=True),
        sa.Column("community", sa.String(length=150), nullable=False),
        sa.Column("directions", sa.Text(), nullable=True),
        sa.Column("location_status", sa.String(length=60), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("sex", sa.String(length=60), nullable=True),
        sa.Column("nationality", sa.String(length=60), nullable=True),
        sa.Column("government_id_type", sa.String(length=40), nullable=True),
        sa.Column("government_id_ciphertext", sa.Text(), nullable=True),
        sa.Column("government_id_hash", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_people_email"), "people", ["email"], unique=False)
    op.create_index(
        op.f("ix_people_government_id_hash"), "people", ["government_id_hash"], unique=False
    )
    op.create_index(op.f("ix_people_normalized_name"), "people", ["normalized_name"], unique=False)
    op.create_index(
        op.f("ix_people_phone_normalized"), "people", ["phone_normalized"], unique=False
    )
    op.create_table(
        "participants",
        sa.Column("participant_code", sa.String(length=40), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("programme_code", sa.String(length=40), nullable=False),
        sa.Column("hamis_id", sa.String(length=100), nullable=True),
        sa.Column("onboarding_status", sa.String(length=30), nullable=False),
        sa.Column("readiness_status", sa.String(length=30), nullable=False),
        sa.Column("availability_status", sa.String(length=30), nullable=False),
        sa.Column("cv_status", sa.String(length=30), nullable=False),
        sa.Column("assigned_user_id", sa.Uuid(), nullable=True),
        sa.Column("owner_assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_type", sa.String(length=60), nullable=True),
        sa.Column("source_detail", sa.String(length=200), nullable=True),
        sa.Column("implementing_partner", sa.String(length=150), nullable=True),
        sa.Column("employment_status", sa.String(length=60), nullable=True),
        sa.Column("current_occupation", sa.String(length=150), nullable=True),
        sa.Column("sector_code", sa.String(length=60), nullable=True),
        sa.Column("industry_code", sa.String(length=60), nullable=True),
        sa.Column("job_type", sa.String(length=60), nullable=True),
        sa.Column("job_role", sa.String(length=150), nullable=True),
        sa.Column("work_region_code", sa.String(length=60), nullable=True),
        sa.Column("work_district_code", sa.String(length=60), nullable=True),
        sa.Column("work_community", sa.String(length=150), nullable=True),
        sa.Column("priority", sa.String(length=15), nullable=False),
        sa.Column("next_action", sa.String(length=500), nullable=True),
        sa.Column("next_action_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_sections", sa.JSON(), nullable=False),
        sa.Column("training_summary", sa.Text(), nullable=True),
        sa.Column("completion_mode", sa.String(length=30), nullable=True),
        sa.Column("assisted_by", sa.Uuid(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_cv_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "availability_status IN ('UNKNOWN','AVAILABLE','TEMPORARILY_UNAVAILABLE','UNAVAILABLE')"
        ),
        sa.CheckConstraint(
            "cv_status IN ('MISSING','UPLOADED','PARSING','REVIEW_REQUIRED','READY','NOT_REQUIRED')"
        ),
        sa.CheckConstraint(
            "onboarding_status IN ('NOT_STARTED','IN_PROGRESS','COMPLETE','BLOCKED','WITHDRAWN')"
        ),
        sa.CheckConstraint(
            "readiness_status IN ('NOT_ASSESSED','DEVELOPING','JOB_READY','NOT_JOB_READY')"
        ),
        sa.ForeignKeyConstraint(
            ["assigned_user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["assisted_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["people.id"],
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hamis_id"),
        sa.UniqueConstraint("participant_code"),
        sa.UniqueConstraint("person_id"),
    )
    op.create_index(
        op.f("ix_participants_assigned_user_id"), "participants", ["assigned_user_id"], unique=False
    )
    op.create_index(
        op.f("ix_participants_onboarding_status"),
        "participants",
        ["onboarding_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_participants_readiness_status"), "participants", ["readiness_status"], unique=False
    )
    op.create_table(
        "consents",
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("consent_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("method", sa.String(length=40), nullable=False),
        sa.Column("privacy_notice_version", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("status != 'WITHDRAWN' OR withdrawn_at IS NOT NULL"),
        sa.CheckConstraint("status IN ('ACTIVE','WITHDRAWN')"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["participants.id"],
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_consents_participant_id"), "consents", ["participant_id"], unique=False
    )
    op.create_table(
        "documents",
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("document_code", sa.String(length=40), nullable=False),
        sa.Column("document_type", sa.String(length=40), nullable=False),
        sa.Column("storage_key", sa.String(length=250), nullable=False),
        sa.Column("original_filename", sa.String(length=200), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("scan_status", sa.String(length=30), nullable=False),
        sa.Column("scan_details", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "scan_status IN ('UPLOAD_PENDING','SCANNING','AVAILABLE','REJECTED','ARCHIVED')"
        ),
        sa.CheckConstraint("size_bytes > 0"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["participants.id"],
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_code"),
        sa.UniqueConstraint("participant_id", "version_number", name="uq_cv_version"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        op.f("ix_documents_participant_id"), "documents", ["participant_id"], unique=False
    )
    op.create_table(
        "participant_education",
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("education_level", sa.String(length=100), nullable=False),
        sa.Column("institution", sa.String(length=200), nullable=True),
        sa.Column("field_of_study", sa.String(length=200), nullable=True),
        sa.Column("start_year", sa.Integer(), nullable=True),
        sa.Column("end_year", sa.Integer(), nullable=True),
        sa.Column("is_highest", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["participants.id"],
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_participant_education_participant_id"),
        "participant_education",
        ["participant_id"],
        unique=False,
    )
    op.create_table(
        "participant_experience",
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("employer_name", sa.String(length=200), nullable=False),
        sa.Column("role_title", sa.String(length=200), nullable=False),
        sa.Column("sector", sa.String(length=60), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["participants.id"],
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_participant_experience_participant_id"),
        "participant_experience",
        ["participant_id"],
        unique=False,
    )
    op.create_table(
        "participant_sensitive_profiles",
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("refugee_status", sa.String(length=60), nullable=True),
        sa.Column("displacement_status", sa.String(length=60), nullable=True),
        sa.Column("displacement_reason", sa.Text(), nullable=True),
        sa.Column("original_community", sa.String(length=150), nullable=True),
        sa.Column("host_community", sa.String(length=150), nullable=True),
        sa.Column("disability_status", sa.String(length=60), nullable=True),
        sa.Column("disability_specify", sa.Text(), nullable=True),
        sa.Column("current_income_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("income_frequency", sa.String(length=20), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("current_income_amount IS NULL OR current_income_amount >= 0"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["participants.id"],
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("participant_id"),
    )
    op.create_table(
        "participant_skills",
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("skill_name", sa.String(length=150), nullable=False),
        sa.Column("skill_code", sa.String(length=60), nullable=True),
        sa.Column("level", sa.String(length=60), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["participants.id"],
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_participant_skills_participant_id"),
        "participant_skills",
        ["participant_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_participant_current_cv", "participants", "documents", ["current_cv_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_participant_current_cv", "participants", type_="foreignkey")
    op.drop_index(op.f("ix_participant_skills_participant_id"), table_name="participant_skills")
    op.drop_table("participant_skills")
    op.drop_table("participant_sensitive_profiles")
    op.drop_index(
        op.f("ix_participant_experience_participant_id"), table_name="participant_experience"
    )
    op.drop_table("participant_experience")
    op.drop_index(
        op.f("ix_participant_education_participant_id"), table_name="participant_education"
    )
    op.drop_table("participant_education")
    op.drop_index(op.f("ix_documents_participant_id"), table_name="documents")
    op.drop_table("documents")
    op.drop_index(op.f("ix_consents_participant_id"), table_name="consents")
    op.drop_table("consents")
    op.drop_index(op.f("ix_participants_readiness_status"), table_name="participants")
    op.drop_index(op.f("ix_participants_onboarding_status"), table_name="participants")
    op.drop_index(op.f("ix_participants_assigned_user_id"), table_name="participants")
    op.drop_table("participants")
    op.drop_index(op.f("ix_people_phone_normalized"), table_name="people")
    op.drop_index(op.f("ix_people_normalized_name"), table_name="people")
    op.drop_index(op.f("ix_people_government_id_hash"), table_name="people")
    op.drop_index(op.f("ix_people_email"), table_name="people")
    op.drop_table("people")
