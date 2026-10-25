"""bind access tokens to the current employee session generation

Revision ID: 0015_session_invalidation
Revises: 0014_staff_management
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015_session_invalidation"
down_revision: str | None = "0014_staff_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "session_version")
