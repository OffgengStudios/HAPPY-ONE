"""Participant dates, independent IDs, baseline and individual training modules."""

import re

import sqlalchemy as sa
from alembic import op

revision = "0040_participant_lifecycle"
down_revision = "0039_operational_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, kind in (
        ("onboarding_date", sa.Date()),
        ("support_type", sa.String(60)),
        ("baseline_employment_status", sa.String(60)),
        ("baseline_occupation", sa.String(150)),
    ):
        op.add_column("participants", sa.Column(name, kind))
    op.add_column("people", sa.Column("voter_id_ciphertext", sa.Text()))
    op.add_column("people", sa.Column("voter_id_hash", sa.String(64)))
    op.create_unique_constraint("uq_people_voter_id_hash", "people", ["voter_id_hash"])
    # Preserve existing ciphertext without decrypting or exporting historical IDs.
    op.execute(
        "UPDATE people SET voter_id_ciphertext=government_id_ciphertext, "
        "voter_id_hash=government_id_hash, government_id_ciphertext=NULL, "
        "government_id_hash=NULL, government_id_type=NULL "
        "WHERE government_id_type='VOTER_ID'"
    )
    for name, kind in (
        ("baseline_income_amount", sa.Numeric(14, 2)),
        ("baseline_income_frequency", sa.String(20)),
        ("baseline_captured_at", sa.DateTime(timezone=True)),
    ):
        op.add_column("participant_sensitive_profiles", sa.Column(name, kind))
    op.add_column("trainings", sa.Column("agriculture_sector", sa.String(60)))
    for name in ("received_modules", "completed_modules"):
        op.add_column(
            "training_attendance", sa.Column(name, sa.JSON(), nullable=False, server_default="[]")
        )
    op.create_table(
        "onboarding_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("participant_id", sa.Uuid(), sa.ForeignKey("participants.id"), nullable=False),
        sa.Column("previous_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_onboarding_revisions_participant_id", "onboarding_revisions", ["participant_id"]
    )
    for name, length in (
        ("placed_by_partner", 150),
        ("placement_region", 60),
        ("placement_district", 60),
        ("placement_community", 150),
        ("sector", 60),
        ("industry", 60),
        ("job_type", 60),
        ("job_role", 150),
        ("employment_type", 20),
        ("employment_category", 20),
        ("employer_name", 200),
        ("contract_type", 60),
        ("work_hours_period", 20),
    ):
        op.add_column("placements", sa.Column(name, sa.String(length)))
    op.add_column("placements", sa.Column("work_hours", sa.Numeric(5, 2)))
    op.alter_column("outcomes", "placement_id", existing_type=sa.Uuid(), nullable=True)
    op.add_column("outcomes", sa.Column("employment_start_date", sa.Date()))
    for name, size in (("employment_type", 20), ("employment_category", 20), ("job_type", 60)):
        op.add_column("outcomes", sa.Column(name, sa.String(size)))
    op.add_column(
        "outcomes", sa.Column("agriculture", sa.JSON(), nullable=False, server_default="{}")
    )


def downgrade() -> None:
    schema = op.get_bind().execute(sa.text("SELECT current_schema()")).scalar_one()
    if not re.fullmatch(r"happy_test_[0-9a-f]{32}", schema):
        raise RuntimeError(
            "Use a forward migration; identity and baseline history must be retained."
        )
    for name in (
        "employment_start_date",
        "employment_type",
        "employment_category",
        "job_type",
        "agriculture",
    ):
        op.drop_column("outcomes", name)
    op.alter_column("outcomes", "placement_id", existing_type=sa.Uuid(), nullable=False)
    for name in (
        "placed_by_partner",
        "placement_region",
        "placement_district",
        "placement_community",
        "sector",
        "industry",
        "job_type",
        "job_role",
        "employment_type",
        "employment_category",
        "employer_name",
        "contract_type",
        "work_hours_period",
        "work_hours",
    ):
        op.drop_column("placements", name)
    op.drop_table("onboarding_revisions")
    for name in ("received_modules", "completed_modules"):
        op.drop_column("training_attendance", name)
    op.drop_column("trainings", "agriculture_sector")
    for name in ("baseline_income_amount", "baseline_income_frequency", "baseline_captured_at"):
        op.drop_column("participant_sensitive_profiles", name)
    op.drop_constraint("uq_people_voter_id_hash", "people", type_="unique")
    op.drop_column("people", "voter_id_hash")
    op.drop_column("people", "voter_id_ciphertext")
    for name in (
        "onboarding_date",
        "support_type",
        "baseline_employment_status",
        "baseline_occupation",
    ):
        op.drop_column("participants", name)
