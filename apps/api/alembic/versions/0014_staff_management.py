"""add forced password change for employee credential resets

Revision ID: 0014_staff_management
Revises: 0013_auth_hardening
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_staff_management"
down_revision: str | None = "0013_auth_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
