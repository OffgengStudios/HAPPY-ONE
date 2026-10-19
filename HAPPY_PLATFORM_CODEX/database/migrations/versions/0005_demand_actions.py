"""Demand action priority, assignment timestamps, and Matching vacancy creation."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_demand_actions"
down_revision: str | None = "0004_demand_reference"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "partnerships",
        sa.Column("priority", sa.String(15), nullable=False, server_default="NORMAL"),
    )
    op.alter_column("partnerships", "priority", server_default=None)
    op.add_column("partnerships", sa.Column("owner_assigned_at", sa.DateTime(timezone=True)))
    op.execute(
        "INSERT INTO role_permissions (role_id,permission_id) "
        "SELECT roles.id,permissions.id FROM roles CROSS JOIN permissions "
        "WHERE roles.code='MATCHING' AND permissions.code='vacancy:create' "
        "ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE role_id IN "
        "(SELECT id FROM roles WHERE code='MATCHING') AND permission_id IN "
        "(SELECT id FROM permissions WHERE code='vacancy:create')"
    )
    op.drop_column("partnerships", "owner_assigned_at")
    op.drop_column("partnerships", "priority")
