"""Grant Marketing read access to linked training records

Revision ID: 0027_marketing_training
Revises: 0026_marketing_training_links
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_marketing_training"
down_revision: str | None = "0026_marketing_training_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id,permission_id) "
            "SELECT roles.id,permissions.id FROM roles,permissions "
            "WHERE roles.code='MARKETING' AND permissions.code='training:view' "
            "ON CONFLICT DO NOTHING"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE role_id IN "
            "(SELECT id FROM roles WHERE code='MARKETING') AND permission_id IN "
            "(SELECT id FROM permissions WHERE code='training:view')"
        )
    )
