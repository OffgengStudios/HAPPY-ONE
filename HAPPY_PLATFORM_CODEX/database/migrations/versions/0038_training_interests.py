"""Keep self-reported training interests separate from recruitment skills."""

import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0038_training_interests"
down_revision: str | None = "0037_unijay_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "participants",
        sa.Column("training_interests", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    schema = op.get_bind().execute(sa.text("SELECT current_schema()")).scalar_one()
    if not re.fullmatch(r"happy_test_[0-9a-f]{32}", schema):
        raise RuntimeError(
            "Use a forward migration; participant training interests must be retained."
        )
    op.drop_column("participants", "training_interests")
