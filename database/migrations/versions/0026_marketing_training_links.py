"""Marketing training links

Revision ID: 0026_marketing_training_links
Revises: 0025_report_export_actor_fks
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_marketing_training_links"
down_revision: str | None = "0025_report_export_actor_fks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("marketing_requests", sa.Column("training_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_marketing_requests_training_id_trainings",
        "marketing_requests",
        "trainings",
        ["training_id"],
        ["id"],
    )
    op.create_index("ix_marketing_requests_training_id", "marketing_requests", ["training_id"])
    op.add_column("campaigns", sa.Column("training_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_campaigns_training_id_trainings",
        "campaigns",
        "trainings",
        ["training_id"],
        ["id"],
    )
    op.create_index("ix_campaigns_training_id", "campaigns", ["training_id"])


def downgrade() -> None:
    op.drop_column("campaigns", "training_id")
    op.drop_column("marketing_requests", "training_id")
