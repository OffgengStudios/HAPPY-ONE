"""Asynchronous report export jobs

Revision ID: 0024_report_export_jobs
Revises: 0023_employer_portal
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_report_export_jobs"
down_revision: str | None = "0023_employer_portal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_export_jobs",
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("kpi_code", sa.String(40), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("include_sensitive", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("storage_key", sa.String(300), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_system", sa.String(30), nullable=False),
        sa.Column("created_via", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCEEDED','FAILED')",
            name="ck_report_export_job_status",
        ),
        sa.CheckConstraint(
            "row_count IS NULL OR row_count >= 0", name="ck_report_export_row_count"
        ),
        sa.CheckConstraint("source_system IN ('INTERNAL','HAMIS','EMPLOYER_PORTAL','API')"),
        sa.CheckConstraint(
            "created_via IN ('STAFF','PARTICIPANT','EMPLOYER','INTEGRATION','SYSTEM')"
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        "ix_report_export_requester_created", "report_export_jobs", ["requested_by", "created_at"]
    )
    op.create_index("ix_report_export_jobs_requested_by", "report_export_jobs", ["requested_by"])
    op.create_index("ix_report_export_jobs_status", "report_export_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("report_export_jobs")
