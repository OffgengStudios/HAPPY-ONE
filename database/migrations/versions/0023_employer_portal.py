"""Employer Portal submission integration

Revision ID: 0023_employer_portal
Revises: 0022_hamis_encryption
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_employer_portal"
down_revision: str | None = "0022_hamis_encryption"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employer_portal_submissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_submission_id", sa.String(200), nullable=False),
        sa.Column("reference_number", sa.String(80), nullable=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("payload_ciphertext", sa.Text(), nullable=False),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("vacancy_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status IN ('NEW','NEEDS_REVIEW','CONVERTED','REJECTED','ARCHIVED')",
            name="ck_employer_submission_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["converted_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_submission_id", name="uq_employer_portal_submission"),
    )
    op.create_index(
        "ix_employer_submission_status_received",
        "employer_portal_submissions",
        ["status", "received_at"],
    )
    for action in ("view", "manage"):
        code = "employer_submission:" + action
        op.execute(
            sa.text(
                "INSERT INTO permissions (id,code,resource,action,description) "
                "VALUES (gen_random_uuid(),:code,'employer_submission',:action,:description)"
            ).bindparams(
                code=code,
                action=action,
                description="Employer Portal submission " + action,
            )
        )
        for role in ("DEMAND", "ADMIN"):
            op.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id,permission_id) "
                    "SELECT roles.id,permissions.id FROM roles,permissions "
                    "WHERE roles.code=:role AND permissions.code=:permission "
                    "ON CONFLICT DO NOTHING"
                ).bindparams(role=role, permission=code)
            )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE resource='employer_submission')"
    )
    op.execute("DELETE FROM permissions WHERE resource='employer_submission'")
    op.drop_table("employer_portal_submissions")
