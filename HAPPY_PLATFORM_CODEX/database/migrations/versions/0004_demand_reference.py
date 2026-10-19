"""Demand reference options and append-only vacancy history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_demand_reference"
down_revision: str | None = "0003_demand"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "demand_reference_data",
        sa.Column("group_code", sa.String(40), primary_key=True),
        sa.Column("code", sa.String(60), primary_key=True),
        sa.Column("label", sa.String(100), nullable=False),
    )
    rows = []
    for group, codes in {
        "priority": ("NORMAL", "HIGH", "URGENT"),
        "salary_frequency": (
            "HOURLY",
            "DAILY",
            "WEEKLY",
            "BIWEEKLY",
            "MONTHLY",
            "OTHER",
        ),
        "closure_reason": (
            "FULLY_FILLED",
            "EMPLOYER_CANCELLED",
            "EMPLOYER_UNAVAILABLE",
            "EMPLOYER_NO_RESPONSE",
            "REQUIREMENTS_CHANGED",
            "RECRUITMENT_UNSUCCESSFUL",
            "OTHER",
        ),
    }.items():
        for code in codes:
            rows.append(
                {
                    "group_code": group,
                    "code": code,
                    "label": code.replace("_", " ").capitalize(),
                }
            )
    op.bulk_insert(
        sa.table(
            "demand_reference_data",
            sa.column("group_code", sa.String),
            sa.column("code", sa.String),
            sa.column("label", sa.String),
        ),
        rows,
    )
    op.execute(
        "CREATE TRIGGER vacancy_changes_append_only BEFORE UPDATE OR DELETE "
        "ON vacancy_changes FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER vacancy_changes_append_only ON vacancy_changes")
    op.drop_table("demand_reference_data")
