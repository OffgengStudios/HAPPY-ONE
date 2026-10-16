"""Users, IAM, revocable sessions, throttles, and immutable audit baseline."""

import json
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

BASELINE = json.loads((Path(__file__).resolve().parents[2] / "seeds" / "iam_v1.json").read_text())
PERMISSION_CODES = BASELINE["permissions"]
ROLE_GRANTS = BASELINE["roles"]
WORKSPACES = BASELINE["workspaces"]

revision = "0002_iam"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None

TABLES = [
    "roles",
    "permissions",
    "users",
    "role_permissions",
    "user_roles",
    "user_permission_overrides",
    "auth_sessions",
    "auth_mfa_challenges",
    "auth_login_throttles",
    "audit_events",
]


def upgrade() -> None:
    # Freeze the schema snapshot here rather than importing mutable future models.
    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_system_role", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_table(
        "permissions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("resource", sa.String(70), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("password_hash", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False),
        sa.Column("primary_role_id", sa.Uuid(), sa.ForeignKey("roles.id")),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    for name, left, right in [
        ("user_roles", "users", "roles"),
        ("role_permissions", "roles", "permissions"),
    ]:
        op.create_table(
            name,
            sa.Column(
                "user_id" if left == "users" else "role_id",
                sa.Uuid(),
                sa.ForeignKey(f"{left}.id"),
                primary_key=True,
            ),
            sa.Column(
                "role_id" if right == "roles" else "permission_id",
                sa.Uuid(),
                sa.ForeignKey(f"{right}.id"),
                primary_key=True,
            ),
        )
    op.create_table(
        "user_permission_overrides",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column(
            "permission_id",
            sa.Uuid(),
            sa.ForeignKey("permissions.id"),
            primary_key=True,
        ),
        sa.Column("effect", sa.String(5), nullable=False),
        sa.CheckConstraint("effect IN ('ALLOW', 'DENY')"),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("device_label", sa.String(120), nullable=False),
        sa.Column("mfa_verified", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_table(
        "auth_mfa_challenges",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("consumed", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_auth_mfa_challenges_user_id", "auth_mfa_challenges", ["user_id"])
    op.create_table(
        "auth_login_throttles",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_code", sa.String(100), nullable=False),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.Uuid()),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Uuid()),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("before_json", sa.JSON()),
        sa.Column("after_json", sa.JSON()),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("ip_address", sa.String(50)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_event_code", "audit_events", ["event_code"])
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])
    roles = {code: uuid4() for code in ROLE_GRANTS}
    permissions = {code: uuid4() for code in PERMISSION_CODES}
    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("id", sa.Uuid()),
            sa.column("code", sa.String()),
            sa.column("name", sa.String()),
            sa.column("description", sa.Text()),
            sa.column("is_system_role", sa.Boolean()),
            sa.column("version", sa.Integer()),
        ),
        [
            {
                "id": id,
                "code": code,
                "name": WORKSPACES.get(code, "Administrator"),
                "description": "Baseline role",
                "is_system_role": True,
                "version": 1,
            }
            for code, id in roles.items()
        ],
    )
    op.bulk_insert(
        sa.table(
            "permissions",
            sa.column("id", sa.Uuid()),
            sa.column("code", sa.String()),
            sa.column("resource", sa.String()),
            sa.column("action", sa.String()),
            sa.column("description", sa.Text()),
        ),
        [
            {
                "id": id,
                "code": code,
                "resource": code.split(":")[0],
                "action": code.split(":")[1],
                "description": code,
            }
            for code, id in permissions.items()
        ],
    )
    op.bulk_insert(
        sa.table(
            "role_permissions",
            sa.column("role_id", sa.Uuid()),
            sa.column("permission_id", sa.Uuid()),
        ),
        [
            {"role_id": roles[role], "permission_id": permissions[code]}
            for role, codes in ROLE_GRANTS.items()
            for code in sorted(codes)
        ],
    )
    op.execute("""CREATE FUNCTION reject_audit_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'Audit events are append-only'; END;
        $$ LANGUAGE plpgsql""")
    op.execute("""CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation()""")


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_append_only ON audit_events")
    op.execute("DROP FUNCTION reject_audit_mutation()")
    for name in reversed(TABLES):
        op.drop_table(name)
