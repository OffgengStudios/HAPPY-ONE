"""Generic external references, controlled provenance, and non-user audit actors."""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "0009_integration_readiness"
down_revision: str | None = "0008_supply_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DOMAIN_TABLES = (
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
)


def upgrade() -> None:
    op.create_table(
        "external_references",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("external_system", sa.String(60), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("external_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "external_system", "entity_type", "external_id", name="uq_external_reference_key"
        ),
        sa.CheckConstraint(
            "entity_type IN ('PARTICIPANT','ORGANIZATION','VACANCY')",
            name="ck_external_reference_entity_type",
        ),
        sa.CheckConstraint(
            "external_system ~ '^[A-Z][A-Z0-9_]{0,59}$'", name="ck_external_reference_system"
        ),
        sa.CheckConstraint(
            "length(trim(external_id)) > 0", name="ck_external_reference_identifier"
        ),
    )
    op.create_index(
        "ix_external_reference_entity", "external_references", ["entity_type", "entity_id"]
    )
    # Preserve only already-local references; this does not connect to or import HAMIS.
    op.execute(
        "INSERT INTO external_references (id,entity_type,entity_id,external_system,external_id,"
        "external_metadata,created_at,updated_at,version) SELECT gen_random_uuid(),"
        "'PARTICIPANT',id,'HAMIS',hamis_id,'{}'::json,created_at,updated_at,1 "
        "FROM participants WHERE hamis_id IS NOT NULL"
    )
    op.drop_column("participants", "hamis_id")
    for table in DOMAIN_TABLES:
        op.add_column(
            table,
            sa.Column("source_system", sa.String(30), nullable=False, server_default="INTERNAL"),
        )
        op.add_column(
            table, sa.Column("created_via", sa.String(30), nullable=False, server_default="STAFF")
        )
        op.create_check_constraint(
            "ck_source_system",
            table,
            "source_system IN ('INTERNAL','HAMIS','EMPLOYER_PORTAL','API')",
        )
        op.create_check_constraint(
            "ck_created_via",
            table,
            "created_via IN ('STAFF','PARTICIPANT','EMPLOYER','INTEGRATION','SYSTEM')",
        )
    op.alter_column(
        "audit_events",
        "actor_id",
        existing_type=sa.Uuid(),
        type_=sa.String(100),
        existing_nullable=True,
        postgresql_using="actor_id::text",
    )
    op.create_check_constraint(
        "ck_audit_actor_type",
        "audit_events",
        "actor_type IN ('USER','PARTICIPANT','EMPLOYER','SYSTEM','INTEGRATION')",
    )
    op.create_check_constraint(
        "ck_audit_actor_identity",
        "audit_events",
        "(actor_type IN ('USER','PARTICIPANT','EMPLOYER') AND actor_id IS NOT NULL "
        "AND actor_id ~ '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        "[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$') OR "
        "(actor_type='SYSTEM' AND (actor_id IS NULL OR actor_id ~ '^[A-Z][A-Z0-9_]{0,99}$')) "
        "OR (actor_type='INTEGRATION' AND actor_id IS NOT NULL "
        "AND actor_id ~ '^[A-Z][A-Z0-9_]{0,99}$')",
    )
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        sa.column("description", sa.String()),
    )
    for action in ("view", "manage"):
        code = "external_reference:" + action
        op.bulk_insert(
            permissions,
            [
                {
                    "id": uuid5(NAMESPACE_URL, "happy/permission/" + code),
                    "code": code,
                    "resource": "external_reference",
                    "action": action,
                    "description": "External reference " + action,
                }
            ],
        )
    op.execute(
        "INSERT INTO role_permissions (role_id,permission_id) SELECT roles.id,permissions.id "
        "FROM roles CROSS JOIN permissions WHERE roles.code='ADMIN' "
        "AND permissions.resource='external_reference'"
    )


def downgrade() -> None:
    # Never discard non-UUID actor attribution just to satisfy the old audit schema.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM audit_events WHERE actor_id IS NOT NULL "
        "AND actor_id !~ '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        "[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$') THEN RAISE EXCEPTION "
        "'Cannot downgrade: non-UUID audit actors must be preserved'; END IF; "
        "IF EXISTS (SELECT 1 FROM external_references WHERE external_system != 'HAMIS' "
        "OR entity_type != 'PARTICIPANT') OR EXISTS (SELECT 1 FROM external_references "
        "GROUP BY entity_id HAVING count(*) > 1) THEN RAISE EXCEPTION "
        "'Cannot downgrade: external references cannot fit the legacy column'; "
        "END IF; END $$"
    )
    op.execute(
        "DELETE FROM user_permission_overrides WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE resource='external_reference')"
    )
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE resource='external_reference')"
    )
    op.execute("DELETE FROM permissions WHERE resource='external_reference'")
    op.drop_constraint("ck_audit_actor_identity", "audit_events", type_="check")
    op.drop_constraint("ck_audit_actor_type", "audit_events", type_="check")
    op.alter_column(
        "audit_events",
        "actor_id",
        existing_type=sa.String(100),
        type_=sa.Uuid(),
        existing_nullable=True,
        postgresql_using="actor_id::uuid",
    )
    for table in reversed(DOMAIN_TABLES):
        op.drop_constraint("ck_source_system", table, type_="check")
        op.drop_constraint("ck_created_via", table, type_="check")
        op.drop_column(table, "source_system")
        op.drop_column(table, "created_via")
    op.add_column("participants", sa.Column("hamis_id", sa.String(100)))
    op.create_unique_constraint("participants_hamis_id_key", "participants", ["hamis_id"])
    op.execute(
        "UPDATE participants SET hamis_id=external_references.external_id FROM external_references "
        "WHERE external_references.entity_id=participants.id "
        "AND external_references.entity_type='PARTICIPANT' "
        "AND external_references.external_system='HAMIS'"
    )
    op.drop_index("ix_external_reference_entity", table_name="external_references")
    op.drop_table("external_references")
