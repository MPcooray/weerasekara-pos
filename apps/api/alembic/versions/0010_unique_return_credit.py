"""prevent duplicate credit notes for one return

Revision ID: 0010_unique_return_credit
Revises: 0009_financial_adjustments
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_unique_return_credit"
down_revision: str | None = "0009_financial_adjustments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("credit_notes") as batch:
        batch.create_unique_constraint("uq_credit_notes_return", ["return_id"])


def downgrade() -> None:
    with op.batch_alter_table("credit_notes") as batch:
        batch.drop_constraint("uq_credit_notes_return", type_="unique")
