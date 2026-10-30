"""Keep an unknown or inapplicable income distinct from zero and an unrecorded value."""

import re

import sqlalchemy as sa
from alembic import op

revision = "0041_income_availability"
down_revision = "0040_participant_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("participant_sensitive_profiles", sa.Column("income_status", sa.String(20)))
    op.add_column(
        "participant_sensitive_profiles", sa.Column("baseline_income_status", sa.String(20))
    )
    op.add_column("outcomes", sa.Column("income_status", sa.String(20)))


def downgrade() -> None:
    schema = op.get_bind().execute(sa.text("SELECT current_schema()")).scalar_one()
    if not re.fullmatch(r"happy_test_[0-9a-f]{32}", schema):
        raise RuntimeError("Use a forward migration; income availability history must be retained.")
    op.drop_column("outcomes", "income_status")
    op.drop_column("participant_sensitive_profiles", "baseline_income_status")
    op.drop_column("participant_sensitive_profiles", "income_status")
