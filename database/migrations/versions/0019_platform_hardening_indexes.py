"""platform hardening indexes

Revision ID: 0019_hardening
Revises: 0018_reporting
Create Date: 2026-10-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019_hardening"
down_revision: str | None = "0018_reporting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_placement_confirmed_at", "placements", ["confirmed_at"])
    op.create_index("ix_placement_actual_start_date", "placements", ["actual_start_date"])
    op.create_index(
        "ix_candidate_history_stage_occurred",
        "candidate_status_history",
        ["to_status", "occurred_at"],
    )
    op.create_index(
        "ix_participant_created_completed", "participants", ["created_at", "completed_at"]
    )
    op.create_index("ix_auth_session_expiry_revoked", "auth_sessions", ["expires_at", "revoked_at"])
    op.create_index(
        "ix_audit_entity_occurred",
        "audit_events",
        ["entity_type", "entity_id", "occurred_at"],
    )
    op.create_index(
        "ix_audit_actor_occurred",
        "audit_events",
        ["actor_type", "actor_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_actor_occurred", table_name="audit_events")
    op.drop_index("ix_audit_entity_occurred", table_name="audit_events")
    op.drop_index("ix_auth_session_expiry_revoked", table_name="auth_sessions")
    op.drop_index("ix_participant_created_completed", table_name="participants")
    op.drop_index("ix_candidate_history_stage_occurred", table_name="candidate_status_history")
    op.drop_index("ix_placement_actual_start_date", table_name="placements")
    op.drop_index("ix_placement_confirmed_at", table_name="placements")
