"""Durable non-PII worker and backup/restore operational checkpoints."""

import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0039_operational_state"
down_revision: str | None = "0038_training_interests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_state",
        sa.Column("component", sa.String(20), primary_key=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_failure_at", sa.DateTime(timezone=True)),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "component IN ('WORKER','BACKUP','RESTORE')", name="ck_operational_component"
        ),
        sa.CheckConstraint("consecutive_failures >= 0", name="ck_operational_failures"),
    )


def downgrade() -> None:
    schema = op.get_bind().execute(sa.text("SELECT current_schema()")).scalar_one()
    if not re.fullmatch(r"happy_test_[0-9a-f]{32}", schema):
        raise RuntimeError("Use a forward migration; operational recovery evidence is retained.")
    op.drop_table("operational_state")
