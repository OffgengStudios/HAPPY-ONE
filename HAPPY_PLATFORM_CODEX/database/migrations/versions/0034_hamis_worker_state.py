"""Add durable HAMIS worker state

Revision ID: 0034_hamis_worker
Revises: 0033_durable_jobs
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034_hamis_worker"
down_revision: str | None = "0033_durable_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_hamis_event_status", "hamis_inbound_events", type_="check")
    op.create_check_constraint(
        "ck_hamis_event_status",
        "hamis_inbound_events",
        "status IN ('RECEIVED','PROCESSING','APPLIED','NEEDS_REVIEW','REJECTED','FAILED')",
    )
    op.add_column(
        "hamis_inbound_events",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("hamis_inbound_events", sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
    op.add_column("hamis_inbound_events", sa.Column("lease_expires_at", sa.DateTime(timezone=True)))
    op.add_column("hamis_inbound_events", sa.Column("lease_owner", sa.String(100)))
    op.add_column("hamis_inbound_events", sa.Column("error_code", sa.String(80)))
    op.add_column("hamis_inbound_events", sa.Column("error_message", sa.String(500)))
    op.create_check_constraint(
        "ck_hamis_event_attempts", "hamis_inbound_events", "attempt_count >= 0"
    )
    op.create_index(
        "ix_hamis_inbound_events_next_attempt_at",
        "hamis_inbound_events",
        ["next_attempt_at"],
    )
    op.create_index(
        "ix_hamis_inbound_events_lease_expires_at",
        "hamis_inbound_events",
        ["lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_hamis_inbound_events_lease_expires_at", table_name="hamis_inbound_events")
    op.drop_index("ix_hamis_inbound_events_next_attempt_at", table_name="hamis_inbound_events")
    op.drop_constraint("ck_hamis_event_attempts", "hamis_inbound_events", type_="check")
    for column in (
        "error_message",
        "error_code",
        "lease_owner",
        "lease_expires_at",
        "next_attempt_at",
        "attempt_count",
    ):
        op.drop_column("hamis_inbound_events", column)
    op.execute("UPDATE hamis_inbound_events SET status = 'RECEIVED' WHERE status = 'PROCESSING'")
    op.drop_constraint("ck_hamis_event_status", "hamis_inbound_events", type_="check")
    op.create_check_constraint(
        "ck_hamis_event_status",
        "hamis_inbound_events",
        "status IN ('RECEIVED','APPLIED','NEEDS_REVIEW','REJECTED','FAILED')",
    )
