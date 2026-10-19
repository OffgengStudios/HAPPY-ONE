"""Protect advisory parser result content from mutation.

Revision ID: 0014_cv_result_immutable
Revises: 0013_cv_parser
Create Date: 2026-10-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014_cv_result_immutable"
down_revision: str | None = "0013_cv_parser"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION protect_cv_parser_result_content() RETURNS trigger AS $$
        BEGIN
            IF NEW.job_id IS DISTINCT FROM OLD.job_id
               OR NEW.schema_version IS DISTINCT FROM OLD.schema_version
               OR NEW.provider IS DISTINCT FROM OLD.provider
               OR NEW.model IS DISTINCT FROM OLD.model
               OR NEW.suggestions_json IS DISTINCT FROM OLD.suggestions_json
               OR NEW.created_at IS DISTINCT FROM OLD.created_at
               OR NEW.source_system IS DISTINCT FROM OLD.source_system
               OR NEW.created_via IS DISTINCT FROM OLD.created_via THEN
                RAISE EXCEPTION 'parser result content is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_cv_parser_result_content_immutable BEFORE UPDATE "
        "ON cv_parser_results FOR EACH ROW EXECUTE FUNCTION protect_cv_parser_result_content()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_cv_parser_result_content_immutable ON cv_parser_results")
    op.execute("DROP FUNCTION IF EXISTS protect_cv_parser_result_content()")
