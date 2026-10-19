"""Add cross-workstream tasks, handoffs, and notifications

Revision ID: 0028_work_management
Revises: 0027_marketing_training
Create Date: 2026-10-15
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "0028_work_management"
down_revision: str | None = "0027_marketing_training"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {
    "task:view": ("task", "view"),
    "task:edit": ("task", "edit"),
    "handoff:view": ("handoff", "view"),
    "handoff:manage": ("handoff", "manage"),
    "notification:view": ("notification", "view"),
    "notification:manage": ("notification", "manage"),
}
STAFF_ROLES = (
    "DEMAND",
    "SUPPLY",
    "MATCHING",
    "MERL",
    "MARKETING",
    "MANAGEMENT",
    "ADMIN",
)


def record_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_system", sa.String(30), nullable=False, server_default="INTERNAL"),
        sa.Column("created_via", sa.String(30), nullable=False, server_default="STAFF"),
        sa.CheckConstraint("source_system IN ('INTERNAL','HAMIS','EMPLOYER_PORTAL','API')"),
        sa.CheckConstraint(
            "created_via IN ('STAFF','PARTICIPANT','EMPLOYER','INTEGRATION','SYSTEM')"
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "tasks",
        *record_columns(),
        sa.Column("task_code", sa.String(40), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("priority", sa.String(10), nullable=False, server_default="NORMAL"),
        sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("owner_team", sa.String(40)),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("entity_id", sa.Uuid()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('OPEN','IN_PROGRESS','BLOCKED','COMPLETED','CANCELLED')",
            name="ck_task_status",
        ),
        sa.CheckConstraint("priority IN ('LOW','NORMAL','HIGH','URGENT')", name="ck_task_priority"),
    )
    op.create_index("ix_task_owner_status_due", "tasks", ["owner_user_id", "status", "due_at"])
    op.create_index("ix_task_team_status_due", "tasks", ["owner_team", "status", "due_at"])
    op.create_index("ix_tasks_entity_id", "tasks", ["entity_id"])
    op.create_index("ix_tasks_owner_user_id", "tasks", ["owner_user_id"])
    op.create_index("ix_tasks_owner_team", "tasks", ["owner_team"])

    op.create_table(
        "handoffs",
        *record_columns(),
        sa.Column("from_workstream", sa.String(40), nullable=False),
        sa.Column("to_workstream", sa.String(40), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="SENT"),
        sa.Column("sent_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_to", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("return_reason", sa.Text()),
        sa.CheckConstraint(
            "status IN ('SENT','ACCEPTED','IN_PROGRESS','COMPLETED','RETURNED','CANCELLED')",
            name="ck_handoff_status",
        ),
    )
    op.create_index("ix_handoff_to_status_sent", "handoffs", ["to_workstream", "status", "sent_at"])
    op.create_index("ix_handoff_assignee_status", "handoffs", ["assigned_to", "status"])
    op.create_index("ix_handoffs_entity_id", "handoffs", ["entity_id"])
    op.create_index("ix_handoffs_assigned_to", "handoffs", ["assigned_to"])

    op.create_table(
        "notifications",
        *record_columns(),
        sa.Column("recipient_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("entity_id", sa.Uuid()),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "kind IN ('TASK_ASSIGNED','HANDOFF_SENT','HANDOFF_ACCEPTED','SYSTEM')",
            name="ck_notification_kind",
        ),
    )
    op.create_index(
        "ix_notification_recipient_read",
        "notifications",
        ["recipient_user_id", "read_at", "created_at"],
    )
    op.create_index("ix_notifications_recipient_user_id", "notifications", ["recipient_user_id"])
    op.create_index("ix_notifications_entity_id", "notifications", ["entity_id"])

    connection = op.get_bind()
    for code, (resource, action) in PERMISSIONS.items():
        connection.execute(
            sa.text(
                "INSERT INTO permissions (id,code,resource,action,description) "
                "VALUES (:id,:code,:resource,:action,:description) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {
                "id": uuid4(),
                "code": code,
                "resource": resource,
                "action": action,
                "description": f"{action.title()} {resource} records",
            },
        )
    connection.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id,permission_id) "
            "SELECT roles.id,permissions.id FROM roles CROSS JOIN permissions "
            "WHERE roles.code = ANY(:roles) "
            "AND permissions.code = ANY(:permissions) ON CONFLICT DO NOTHING"
        ),
        {
            "roles": list(STAFF_ROLES),
            "permissions": [code for code in PERMISSIONS if code != "notification:manage"],
        },
    )
    connection.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id,permission_id) "
            "SELECT roles.id,permissions.id FROM roles CROSS JOIN permissions "
            "WHERE roles.code='ADMIN' AND permissions.code='notification:manage' "
            "ON CONFLICT DO NOTHING"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE code = ANY(:codes))"
        ).bindparams(codes=list(PERMISSIONS))
    )
    op.execute(
        sa.text("DELETE FROM permissions WHERE code = ANY(:codes)").bindparams(
            codes=list(PERMISSIONS)
        )
    )
    op.drop_table("notifications")
    op.drop_table("handoffs")
    op.drop_table("tasks")
