"""Report export audit actor foreign keys

Revision ID: 0025_report_export_actor_fks
Revises: 0024_report_export_jobs
Create Date: 2026-10-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0025_report_export_actor_fks"
down_revision: str | None = "0024_report_export_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_report_export_jobs_created_by_users",
        "report_export_jobs",
        "users",
        ["created_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_report_export_jobs_updated_by_users",
        "report_export_jobs",
        "users",
        ["updated_by"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_report_export_jobs_updated_by_users",
        "report_export_jobs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_report_export_jobs_created_by_users",
        "report_export_jobs",
        type_="foreignkey",
    )
