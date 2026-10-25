"""add login lockout and access-token revocation

Revision ID: 0013_auth_hardening
Revises: 0012_optical_orders
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_auth_hardening"
down_revision: str | None = "0012_optical_orders"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("failed_login_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True)))
    op.create_table(
        "revoked_access_tokens",
        sa.Column("jti", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_revoked_access_tokens_user_id", "revoked_access_tokens", ["user_id"])
    op.create_index(
        "ix_revoked_access_tokens_tenant_id", "revoked_access_tokens", ["tenant_id"]
    )
    op.create_index(
        "ix_revoked_access_tokens_expires_at", "revoked_access_tokens", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_table("revoked_access_tokens")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
