"""A signed MOU state always records its signed date, including optional MOUs."""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_mou_signed_date"
down_revision: str | None = "0005_demand_actions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_partnership_signed_date",
        "partnerships",
        "status != 'MOU_SIGNED' OR mou_signed_at IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_partnership_signed_date", "partnerships", type_="check")
