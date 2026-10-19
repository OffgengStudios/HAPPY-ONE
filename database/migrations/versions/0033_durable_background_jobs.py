"""Add durable report export worker state

Revision ID: 0033_durable_jobs
Revises: 0032_partner_docs
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033_durable_jobs"
down_revision: str | None = "0032_partner_docs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "report_export_jobs",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("report_export_jobs", sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
    op.add_column("report_export_jobs", sa.Column("lease_expires_at", sa.DateTime(timezone=True)))
    op.add_column("report_export_jobs", sa.Column("lease_owner", sa.String(100)))
    op.create_check_constraint(
        "ck_report_export_job_attempts", "report_export_jobs", "attempt_count >= 0"
    )
    op.create_index(
        "ix_report_export_jobs_next_attempt_at", "report_export_jobs", ["next_attempt_at"]
    )
    op.create_index(
        "ix_report_export_jobs_lease_expires_at", "report_export_jobs", ["lease_expires_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_report_export_jobs_lease_expires_at", table_name="report_export_jobs")
    op.drop_index("ix_report_export_jobs_next_attempt_at", table_name="report_export_jobs")
    op.drop_constraint("ck_report_export_job_attempts", "report_export_jobs", type_="check")
    op.drop_column("report_export_jobs", "lease_owner")
    op.drop_column("report_export_jobs", "lease_expires_at")
    op.drop_column("report_export_jobs", "next_attempt_at")
    op.drop_column("report_export_jobs", "attempt_count")
