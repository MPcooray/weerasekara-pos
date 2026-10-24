"""add immutable payment creation timestamp

Revision ID: 0008_payment_timestamps
Revises: 0007_checkout_stock
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_payment_timestamps"
down_revision: str | None = "0007_checkout_stock"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_payments_created_at", "payments", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_payments_created_at", table_name="payments")
    op.drop_column("payments", "created_at")
