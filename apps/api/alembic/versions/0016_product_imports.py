"""add guarded product import previews and results

Revision ID: 0016_product_imports
Revises: 0015_session_invalidation
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016_product_imports"
down_revision: str | None = "0015_session_invalidation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_imports",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("confirmation_key", sa.String(100)),
        sa.Column("template_version", sa.String(20), nullable=False),
        sa.Column(
            "mode",
            sa.Enum("CREATE_ONLY", "UPDATE_EXISTING", name="productimportmode"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("PREVIEWED", "COMPLETED", "FAILED", name="productimportstatus"),
            nullable=False,
        ),
        sa.Column("rows_payload", sa.JSON(), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("valid_rows", sa.Integer(), nullable=False),
        sa.Column("invalid_rows", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("stock_movements_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "confirmation_key", name="uq_product_import_confirmation"),
        sa.UniqueConstraint("token_hash"),
    )
    for column in ("tenant_id", "actor_id", "status", "expires_at"):
        op.create_index(f"ix_product_imports_{column}", "product_imports", [column])


def downgrade() -> None:
    op.drop_table("product_imports")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="productimportstatus").drop(bind, checkfirst=True)
        sa.Enum(name="productimportmode").drop(bind, checkfirst=True)
