"""HAMIS inbound integration boundary

Revision ID: 0021_hamis
Revises: 0020_training
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_hamis"
down_revision: str | None = "0020_training"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hamis_inbound_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_event_id", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("payload_json", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("participant_id", sa.Uuid(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('PARTICIPANT_UPSERT','CONSENT_RECORDED',"
            "'TRAINING_RECORDED','PLACEMENT_RECORDED')",
            name="ck_hamis_event_type",
        ),
        sa.CheckConstraint(
            "status IN ('RECEIVED','APPLIED','NEEDS_REVIEW','REJECTED','FAILED')",
            name="ck_hamis_event_status",
        ),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_event_id", name="uq_hamis_inbound_event"),
    )
    op.create_index(
        "ix_hamis_event_status_received",
        "hamis_inbound_events",
        ["status", "received_at"],
    )
    op.create_index(
        "ix_hamis_inbound_events_participant_id",
        "hamis_inbound_events",
        ["participant_id"],
    )
    for action in ("view", "manage"):
        code = "integration_event:" + action
        op.execute(
            sa.text(
                "INSERT INTO permissions (id,code,resource,action,description) "
                "VALUES (gen_random_uuid(),:code,'integration_event',:action,:description)"
            ).bindparams(code=code, action=action, description="Integration event " + action)
        )
        op.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id,permission_id) "
                "SELECT roles.id,permissions.id FROM roles,permissions "
                "WHERE roles.code='ADMIN' AND permissions.code=:permission "
                "ON CONFLICT DO NOTHING"
            ).bindparams(permission=code)
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE resource='integration_event')"
    )
    op.execute("DELETE FROM permissions WHERE resource='integration_event'")
    op.drop_table("hamis_inbound_events")
