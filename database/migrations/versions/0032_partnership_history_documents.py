"""Add partnership history and private agreement/JD versions

Revision ID: 0032_partner_docs
Revises: 0031_oidc_sso
Create Date: 2026-10-18
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0032_partner_docs"
down_revision: str | None = "0031_oidc_sso"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {
    "partnership_document:view": ("partnership_document", "view"),
    "partnership_document:edit": ("partnership_document", "edit"),
    "partnership_document:download": ("partnership_document", "download"),
    "job_description:view": ("job_description", "view"),
    "job_description:edit": ("job_description", "edit"),
    "job_description:download": ("job_description", "download"),
}


def record_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_system", sa.String(30), server_default="INTERNAL", nullable=False),
        sa.Column("created_via", sa.String(30), server_default="STAFF", nullable=False),
        sa.CheckConstraint("source_system IN ('INTERNAL','HAMIS','EMPLOYER_PORTAL','API')"),
        sa.CheckConstraint(
            "created_via IN ('STAFF','PARTICIPANT','EMPLOYER','INTEGRATION','SYSTEM')"
        ),
    ]


def document_columns(owner: str, target: str, unique_name: str) -> list[sa.Column]:
    return [
        *record_columns(),
        sa.Column(owner, sa.Uuid(), sa.ForeignKey(target), nullable=False),
        sa.Column("document_code", sa.String(40), nullable=False, unique=True),
        sa.Column("storage_key", sa.String(300), nullable=False, unique=True),
        sa.Column("original_filename", sa.String(200), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("scan_status", sa.String(30), nullable=False),
        sa.Column("scan_details", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "scan_status IN ('SCANNING','AVAILABLE','REJECTED','ARCHIVED')",
            name=f"ck_{unique_name}_scan_status",
        ),
        sa.CheckConstraint("size_bytes > 0", name=f"ck_{unique_name}_size"),
        sa.UniqueConstraint(owner, "version_number", name=f"uq_{unique_name}_version"),
    ]


def upgrade() -> None:
    op.drop_constraint("partnerships_organization_id_key", "partnerships", type_="unique")
    op.add_column("partnerships", sa.Column("partnership_code", sa.String(40)))
    op.add_column(
        "partnerships",
        sa.Column("partnership_type", sa.String(20), server_default="RECRUITMENT"),
    )
    op.add_column("partnerships", sa.Column("start_date", sa.Date()))
    op.add_column("partnerships", sa.Column("end_date", sa.Date()))
    op.execute(
        "UPDATE partnerships SET partnership_code = 'PAR-' || "
        "upper(substr(replace(id::text, '-', ''), 1, 12)), start_date = created_at::date"
    )
    op.alter_column("partnerships", "partnership_code", nullable=False)
    op.alter_column("partnerships", "partnership_type", nullable=False, server_default=None)
    op.alter_column("partnerships", "start_date", nullable=False)
    op.create_unique_constraint("uq_partnership_code", "partnerships", ["partnership_code"])
    op.create_index("ix_partnerships_organization_id", "partnerships", ["organization_id"])
    op.create_check_constraint(
        "ck_partnership_type",
        "partnerships",
        "partnership_type IN ('TRAINING','RECRUITMENT','COMBINED')",
    )
    op.create_check_constraint(
        "ck_partnership_dates", "partnerships", "end_date IS NULL OR end_date >= start_date"
    )

    op.create_table(
        "partnership_documents",
        *document_columns("partnership_id", "partnerships.id", "partnership_document"),
    )
    op.create_index(
        "ix_partnership_documents_partnership_id", "partnership_documents", ["partnership_id"]
    )
    op.create_table(
        "job_description_versions",
        *document_columns("vacancy_id", "vacancies.id", "job_description"),
    )
    op.create_index(
        "ix_job_description_versions_vacancy_id", "job_description_versions", ["vacancy_id"]
    )

    for code, (resource, action) in PERMISSIONS.items():
        op.execute(
            sa.text(
                "INSERT INTO permissions (id,code,resource,action,description) "
                "VALUES (:id,:code,:resource,:action,:description)"
            ).bindparams(
                id=uuid4(),
                code=code,
                resource=resource,
                action=action,
                description=f"{action.title()} {resource.replace('_', ' ')}",
            )
        )
    op.execute(
        "INSERT INTO role_permissions (role_id,permission_id) "
        "SELECT roles.id,permissions.id FROM roles CROSS JOIN permissions WHERE "
        "(roles.code IN ('ADMIN','DEMAND') AND permissions.code IN "
        "('partnership_document:view','partnership_document:edit',"
        "'partnership_document:download','job_description:view','job_description:edit',"
        "'job_description:download')) OR "
        "(roles.code='MATCHING' AND permissions.code IN "
        "('job_description:view','job_description:download')) OR "
        "(roles.code='MANAGEMENT' AND permissions.code IN "
        "('partnership_document:view','partnership_document:download',"
        "'job_description:view','job_description:download'))"
    )


def downgrade() -> None:
    codes = ",".join(f"'{code}'" for code in PERMISSIONS)
    op.execute(
        f"DELETE FROM role_permissions WHERE permission_id IN "
        f"(SELECT id FROM permissions WHERE code IN ({codes}))"
    )
    op.execute(f"DELETE FROM permissions WHERE code IN ({codes})")
    op.drop_table("job_description_versions")
    op.drop_table("partnership_documents")
    op.drop_constraint("ck_partnership_dates", "partnerships", type_="check")
    op.drop_constraint("ck_partnership_type", "partnerships", type_="check")
    op.drop_index("ix_partnerships_organization_id", table_name="partnerships")
    op.drop_constraint("uq_partnership_code", "partnerships", type_="unique")
    op.execute(
        "DELETE FROM partnerships a USING partnerships b "
        "WHERE a.organization_id=b.organization_id AND "
        "(a.start_date, a.created_at, a.id) < (b.start_date, b.created_at, b.id)"
    )
    op.drop_column("partnerships", "end_date")
    op.drop_column("partnerships", "start_date")
    op.drop_column("partnerships", "partnership_type")
    op.drop_column("partnerships", "partnership_code")
    op.create_unique_constraint(
        "partnerships_organization_id_key", "partnerships", ["organization_id"]
    )
