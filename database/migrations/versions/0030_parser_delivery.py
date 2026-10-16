"""Add durable CV parser job leasing and retry schedule

Revision ID: 0030_parser_delivery
Revises: 0029_totp_mfa
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_parser_delivery"
down_revision: str | None = "0029_totp_mfa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cv_parser_jobs", sa.Column("next_attempt_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "cv_parser_jobs", sa.Column("lease_expires_at", sa.DateTime(timezone=True))
    )
    op.add_column("cv_parser_jobs", sa.Column("lease_owner", sa.String(100)))
    op.create_index(
        "ix_cv_parser_jobs_next_attempt_at", "cv_parser_jobs", ["next_attempt_at"]
    )
    op.create_index(
        "ix_cv_parser_jobs_lease_expires_at", "cv_parser_jobs", ["lease_expires_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_cv_parser_jobs_lease_expires_at", table_name="cv_parser_jobs")
    op.drop_index("ix_cv_parser_jobs_next_attempt_at", table_name="cv_parser_jobs")
    op.drop_column("cv_parser_jobs", "lease_owner")
    op.drop_column("cv_parser_jobs", "lease_expires_at")
    op.drop_column("cv_parser_jobs", "next_attempt_at")
