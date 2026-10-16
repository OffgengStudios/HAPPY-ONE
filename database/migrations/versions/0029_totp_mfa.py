"""Add encrypted TOTP MFA factors and recovery codes

Revision ID: 0029_totp_mfa
Revises: 0028_work_management
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029_totp_mfa"
down_revision: str | None = "0028_work_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("mfa_secret_ciphertext", sa.Text()))
    op.add_column("users", sa.Column("mfa_pending_secret_ciphertext", sa.Text()))
    op.add_column(
        "users",
        sa.Column(
            "mfa_recovery_hashes", sa.JSON(), nullable=False, server_default="[]"
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "mfa_recovery_hashes")
    op.drop_column("users", "mfa_pending_secret_ciphertext")
    op.drop_column("users", "mfa_secret_ciphertext")
