"""Prevent concurrent duplicate protected identity references without changing UUIDs."""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_supply_identity_unique"
down_revision: str | None = "0009_integration_readiness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_person_government_id_hash", "people", ["government_id_hash"])


def downgrade() -> None:
    op.drop_constraint("uq_person_government_id_hash", "people", type_="unique")
