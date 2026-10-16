"""training domain

Revision ID: 0020_training
Revises: 0019_hardening
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_training"
down_revision: str | None = "0019_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def record_columns():
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_system", sa.String(30), server_default="INTERNAL", nullable=False),
        sa.Column("created_via", sa.String(30), server_default="STAFF", nullable=False),
        sa.CheckConstraint("source_system IN ('INTERNAL','HAMIS','EMPLOYER_PORTAL','API')"),
        sa.CheckConstraint(
            "created_via IN ('STAFF','PARTICIPANT','EMPLOYER','INTEGRATION','SYSTEM')"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    ]


def upgrade() -> None:
    op.create_table(
        "trainings",
        *record_columns(),
        sa.Column("training_code", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("training_type", sa.String(60), nullable=False),
        sa.Column("partner_organization_id", sa.Uuid(), nullable=True),
        sa.Column("trainer_type", sa.String(30), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("location_region_code", sa.String(60), nullable=True),
        sa.Column("location_district_code", sa.String(60), nullable=True),
        sa.Column("location_community", sa.String(150), nullable=True),
        sa.Column("location_text", sa.Text(), nullable=True),
        sa.Column("virtual_platform", sa.String(120), nullable=True),
        sa.Column("modules_json", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.CheckConstraint("mode IN ('IN_PERSON','VIRTUAL','HYBRID')", name="ck_training_mode"),
        sa.CheckConstraint(
            "trainer_type IN ('INTERNAL','EXTERNAL_PARTNER')",
            name="ck_training_trainer_type",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','PLANNED','IN_PROGRESS','COMPLETED','CANCELLED')",
            name="ck_training_status",
        ),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_training_dates"),
        sa.ForeignKeyConstraint(["partner_organization_id"], ["organizations.id"]),
        sa.UniqueConstraint("training_code"),
    )
    op.create_index(
        "ix_trainings_partner_organization_id", "trainings", ["partner_organization_id"]
    )
    op.create_index("ix_trainings_status", "trainings", ["status"])
    op.create_index("ix_training_status_start", "trainings", ["status", "start_date"])
    op.create_table(
        "training_attendance",
        *record_columns(),
        sa.Column("training_id", sa.Uuid(), nullable=False),
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("attendance_status", sa.String(20), nullable=False),
        sa.Column("completion_status", sa.String(20), nullable=False),
        sa.Column("certificate_issued", sa.Boolean(), nullable=False),
        sa.Column("certificate_document_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "attendance_status IN ('PRESENT','ABSENT','LATE','EXCUSED')",
            name="ck_training_attendance_status",
        ),
        sa.CheckConstraint(
            "completion_status IN ('NOT_STARTED','IN_PROGRESS','COMPLETED','NOT_COMPLETED')",
            name="ck_training_completion_status",
        ),
        sa.ForeignKeyConstraint(["training_id"], ["trainings.id"]),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"]),
        sa.ForeignKeyConstraint(["certificate_document_id"], ["documents.id"]),
        sa.UniqueConstraint("training_id", "participant_id", name="uq_training_participant"),
    )
    op.create_index("ix_training_attendance_training_id", "training_attendance", ["training_id"])
    op.create_index(
        "ix_training_attendance_participant_id",
        "training_attendance",
        ["participant_id"],
    )
    for action in ("view", "edit"):
        code = "training:" + action
        op.execute(
            sa.text(
                "INSERT INTO permissions (id,code,resource,action,description) "
                "VALUES (gen_random_uuid(),:code,'training',:action,:description)"
            ).bindparams(code=code, action=action, description="Training " + action)
        )
    for role in ("SUPPLY", "MERL", "ADMIN"):
        for action in ("view", "edit"):
            op.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id,permission_id) "
                    "SELECT roles.id,permissions.id FROM roles,permissions "
                    "WHERE roles.code=:role AND permissions.code=:permission "
                    "ON CONFLICT DO NOTHING"
                ).bindparams(role=role, permission="training:" + action)
            )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id,permission_id) "
            "SELECT roles.id,permissions.id FROM roles,permissions "
            "WHERE roles.code='MANAGEMENT' AND permissions.code='training:view' "
            "ON CONFLICT DO NOTHING"
        )
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE resource='training')"
    )
    op.execute("DELETE FROM permissions WHERE resource='training'")
    op.drop_table("training_attendance")
    op.drop_table("trainings")
