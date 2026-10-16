"""CV parser jobs, advisory results, and human review.

Revision ID: 0013_cv_parser
Revises: 0012_placement
Create Date: 2026-10-10
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "0013_cv_parser"
down_revision: str | None = "0012_placement"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = ("cv_parse:view", "cv_parse:run", "cv_parse:review")


def provenance_columns() -> list[sa.Column]:
    return [
        sa.Column("source_system", sa.String(30), server_default="INTERNAL", nullable=False),
        sa.Column("created_via", sa.String(30), server_default="STAFF", nullable=False),
    ]


def provenance_constraints() -> list[sa.CheckConstraint]:
    return [
        sa.CheckConstraint(
            "source_system IN ('INTERNAL','HAMIS','EMPLOYER_PORTAL','API')",
            name="ck_source_system",
        ),
        sa.CheckConstraint(
            "created_via IN ('STAFF','PARTICIPANT','EMPLOYER','INTEGRATION','SYSTEM')",
            name="ck_created_via",
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "cv_parser_jobs",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(100), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("input_categories", sa.JSON(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(60), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        *provenance_columns(),
        sa.CheckConstraint(
            "status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_cv_parser_job_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_cv_parser_job_attempts"),
        *provenance_constraints(),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
    )
    op.create_index("ix_cv_parser_jobs_document_id", "cv_parser_jobs", ["document_id"])
    op.create_index("ix_cv_parser_jobs_status", "cv_parser_jobs", ["status"])
    op.create_index(
        "uq_cv_parser_active_document",
        "cv_parser_jobs",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('QUEUED','RUNNING') AND archived_at IS NULL"),
    )
    op.create_table(
        "cv_parser_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("schema_version", sa.String(30), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("suggestions_json", sa.JSON(), nullable=False),
        sa.Column("review_status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        *provenance_columns(),
        sa.CheckConstraint(
            "review_status IN ('PENDING_REVIEW','PARTIALLY_REVIEWED','APPROVED','REJECTED')",
            name="ck_cv_parser_result_review_status",
        ),
        *provenance_constraints(),
        sa.ForeignKeyConstraint(["job_id"], ["cv_parser_jobs.id"]),
    )
    op.create_table(
        "cv_parser_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("result_id", sa.Uuid(), nullable=False),
        sa.Column("field", sa.String(100), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("original_value_json", sa.JSON(), nullable=False),
        sa.Column("approved_value_json", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        *provenance_columns(),
        sa.CheckConstraint(
            "decision IN ('APPROVE','REJECT','EDIT')",
            name="ck_cv_parser_review_decision",
        ),
        *provenance_constraints(),
        sa.ForeignKeyConstraint(["result_id"], ["cv_parser_results.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.UniqueConstraint("result_id", "field", name="uq_cv_parser_review_field"),
    )
    op.create_index("ix_cv_parser_reviews_result_id", "cv_parser_reviews", ["result_id"])
    op.execute(
        "CREATE TRIGGER trg_cv_parser_reviews_append_only BEFORE UPDATE OR DELETE "
        "ON cv_parser_reviews FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation()"
    )
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        sa.column("description", sa.String()),
    )
    op.bulk_insert(
        permissions,
        [
            {
                "id": uuid5(NAMESPACE_URL, "happy/permission/" + code),
                "code": code,
                "resource": code.split(":")[0],
                "action": code.split(":")[1],
                "description": code,
            }
            for code in PERMISSIONS
        ],
    )
    op.execute(
        "INSERT INTO role_permissions (role_id,permission_id) "
        "SELECT roles.id,permissions.id FROM roles CROSS JOIN permissions "
        "WHERE permissions.code IN ('cv_parse:view','cv_parse:run','cv_parse:review') "
        "AND roles.code IN ('ADMIN','SUPPLY') ON CONFLICT DO NOTHING"
    )
    op.execute(
        "INSERT INTO role_permissions (role_id,permission_id) "
        "SELECT roles.id,permissions.id FROM roles CROSS JOIN permissions "
        "WHERE permissions.code='cv_parse:view' AND roles.code='MATCHING' ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code IN "
        "('cv_parse:view','cv_parse:run','cv_parse:review'))"
    )
    op.execute(
        "DELETE FROM user_permission_overrides WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code IN "
        "('cv_parse:view','cv_parse:run','cv_parse:review'))"
    )
    op.execute(
        "DELETE FROM permissions WHERE code IN ('cv_parse:view','cv_parse:run','cv_parse:review')"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_cv_parser_reviews_append_only ON cv_parser_reviews")
    op.drop_index("ix_cv_parser_reviews_result_id", table_name="cv_parser_reviews")
    op.drop_table("cv_parser_reviews")
    op.drop_table("cv_parser_results")
    op.drop_index("uq_cv_parser_active_document", table_name="cv_parser_jobs")
    op.drop_index("ix_cv_parser_jobs_status", table_name="cv_parser_jobs")
    op.drop_index("ix_cv_parser_jobs_document_id", table_name="cv_parser_jobs")
    op.drop_table("cv_parser_jobs")
