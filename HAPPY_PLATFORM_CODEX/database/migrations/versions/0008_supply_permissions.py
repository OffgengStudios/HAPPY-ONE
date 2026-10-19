"""Explicit sensitive writes and CV downloads, without changing the original IAM seed."""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "0008_supply_permissions"
down_revision: str | None = "0007_supply"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        sa.column("description", sa.String()),
    )
    for code in ("participant_sensitive:edit", "cv:download"):
        resource, action = code.split(":")
        op.bulk_insert(
            permissions,
            [
                {
                    "id": uuid5(NAMESPACE_URL, "happy/permission/" + code),
                    "code": code,
                    "resource": resource,
                    "action": action,
                    "description": code,
                }
            ],
        )
    op.execute(
        "INSERT INTO role_permissions (role_id,permission_id) SELECT roles.id,permissions.id FROM roles CROSS JOIN permissions WHERE (roles.code='ADMIN' AND permissions.code IN ('participant_sensitive:edit','cv:download')) OR (roles.code IN ('SUPPLY','MATCHING') AND permissions.code='cv:download') ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code IN ('participant_sensitive:edit','cv:download'))"
    )
    op.execute(
        "DELETE FROM user_permission_overrides WHERE permission_id IN (SELECT id FROM permissions WHERE code IN ('participant_sensitive:edit','cv:download'))"
    )
    op.execute("DELETE FROM permissions WHERE code IN ('participant_sensitive:edit','cv:download')")
