"""Encrypt HAMIS event payloads at rest

Revision ID: 0022_hamis_encryption
Revises: 0021_hamis
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "0022_hamis_encryption"
down_revision: str | None = "0021_hamis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if not context.is_offline_mode():
        connection = op.get_bind()
        existing = connection.scalar(sa.text("SELECT count(*) FROM hamis_inbound_events"))
        if existing:
            raise RuntimeError("Apply HAMIS payload encryption before accepting inbound events.")
    op.add_column(
        "hamis_inbound_events",
        sa.Column("payload_ciphertext", sa.Text(), nullable=True),
    )
    op.drop_column("hamis_inbound_events", "payload_json")
    op.alter_column("hamis_inbound_events", "payload_ciphertext", nullable=False)


def downgrade() -> None:
    op.add_column(
        "hamis_inbound_events",
        sa.Column("payload_json", sa.JSON(), nullable=True),
    )
    op.drop_column("hamis_inbound_events", "payload_ciphertext")
