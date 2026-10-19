"""Preserve employer-submitted vacancy benefits and deadline."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036_vacancy_terms"
down_revision: str | None = "0035_public_intake"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("vacancies", sa.Column("deadline", sa.Date()))
    op.add_column(
        "vacancies", sa.Column("benefits", sa.JSON(), nullable=False, server_default="[]")
    )


def downgrade() -> None:
    # Migration-replay tests use disposable, randomly named schemas only.
    # Application environments must use forward migrations to retain evidence.
    import re

    schema = op.get_bind().execute(sa.text("SELECT current_schema()")).scalar_one()
    if not re.fullmatch(r"happy_test_[0-9a-f]{32}", schema):
        raise RuntimeError("Use a forward migration; application evidence is retained.")
    op.drop_column("vacancies", "benefits")
    op.drop_column("vacancies", "deadline")
