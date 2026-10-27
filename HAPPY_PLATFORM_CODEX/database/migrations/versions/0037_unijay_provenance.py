"""Add UNIJAY provenance without rewriting historical source attribution."""

import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037_unijay_provenance"
down_revision: str | None = "0036_vacancy_terms"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DOMAIN_TABLES = [
    "organizations",
    "organization_contacts",
    "partnerships",
    "vacancies",
    "vacancy_requirements",
    "people",
    "participants",
    "consents",
    "documents",
    "participant_education",
    "participant_experience",
    "participant_sensitive_profiles",
    "participant_skills",
]


def upgrade() -> None:
    for table in DOMAIN_TABLES:
        op.drop_constraint("ck_source_system", table, type_="check")
        op.create_check_constraint(
            "ck_source_system",
            table,
            "source_system IN ('INTERNAL','HAMIS','EMPLOYER_PORTAL','API','UNIJAY_FASHION')",
        )
    op.drop_constraint("ck_public_intake_source", "public_intakes", type_="check")
    op.create_check_constraint(
        "ck_public_intake_source",
        "public_intakes",
        "source IN ('HAMIS','EMPLOYER_INTAKE','UNIJAY_FASHION')",
    )


def downgrade() -> None:
    schema = op.get_bind().execute(sa.text("SELECT current_schema()")).scalar_one()
    if not re.fullmatch(r"happy_test_[0-9a-f]{32}", schema):
        raise RuntimeError("Use a forward migration; UNIJAY provenance must be preserved.")
    for table in DOMAIN_TABLES:
        op.drop_constraint("ck_source_system", table, type_="check")
        op.create_check_constraint(
            "ck_source_system",
            table,
            "source_system IN ('INTERNAL','HAMIS','EMPLOYER_PORTAL','API')",
        )
    op.drop_constraint("ck_public_intake_source", "public_intakes", type_="check")
    op.create_check_constraint(
        "ck_public_intake_source",
        "public_intakes",
        "source IN ('HAMIS','EMPLOYER_INTAKE')",
    )
