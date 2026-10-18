"""Add OIDC state and external user identities

Revision ID: 0031_oidc_sso
Revises: 0030_parser_delivery
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031_oidc_sso"
down_revision: str | None = "0030_parser_delivery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_oidc_states",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("nonce_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_auth_oidc_states_expires_at", "auth_oidc_states", ["expires_at"])
    op.create_table(
        "user_external_identities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("email_at_link", sa.String(254), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("provider", "subject", name="uq_external_identity_subject"),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_external_identity_provider"),
    )
    op.create_index("ix_user_external_identities_user_id", "user_external_identities", ["user_id"])


def downgrade() -> None:
    op.drop_table("user_external_identities")
    op.drop_table("auth_oidc_states")
