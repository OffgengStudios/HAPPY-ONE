"""Public intake receipts and private staged files; no participant accounts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0035_public_intake"
down_revision: str | None = "0034_hamis_worker"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "public_intakes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("payload_ciphertext", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("participant_id", sa.Uuid(), sa.ForeignKey("participants.id")),
        sa.Column(
            "employer_submission_id", sa.Uuid(), sa.ForeignKey("employer_portal_submissions.id")
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source", "submission_id", name="uq_public_intake_submission"),
        sa.CheckConstraint("source IN ('HAMIS','EMPLOYER_INTAKE')", name="ck_public_intake_source"),
        sa.CheckConstraint(
            "status IN ('RECEIVED','NEEDS_REVIEW','APPLIED','REJECTED')",
            name="ck_public_intake_status",
        ),
    )
    op.create_index("ix_public_intakes_status", "public_intakes", ["status"])
    op.create_table(
        "intake_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("intake_id", sa.Uuid(), sa.ForeignKey("public_intakes.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("vacancy_index", sa.Integer()),
        sa.Column("storage_key", sa.String(300), nullable=False, unique=True),
        sa.Column("original_filename", sa.String(200), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("scan_status", sa.String(20), nullable=False),
        sa.Column("linked_document_id", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('CV','MOU','AGREEMENT','JD','SUPPORTING')", name="ck_intake_document_kind"
        ),
        sa.CheckConstraint(
            "scan_status IN ('SCANNING','AVAILABLE','REJECTED','ARCHIVED')",
            name="ck_intake_document_scan",
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_intake_document_size"),
    )
    op.create_index("ix_intake_documents_intake_id", "intake_documents", ["intake_id"])


def downgrade() -> None:
    # Migration-replay tests use disposable, randomly named schemas only.
    # Application environments must use forward migrations to retain evidence.
    import re

    schema = op.get_bind().execute(sa.text("SELECT current_schema()")).scalar_one()
    if not re.fullmatch(r"happy_test_[0-9a-f]{32}", schema):
        raise RuntimeError("Use a forward migration; application evidence is retained.")
    op.drop_index("ix_intake_documents_intake_id", table_name="intake_documents")
    op.drop_table("intake_documents")
    op.drop_index("ix_public_intakes_status", table_name="public_intakes")
    op.drop_table("public_intakes")
