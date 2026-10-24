"""add tenant print branding

Revision ID: 0011_tenant_print_branding
Revises: 0010_unique_return_credit
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_tenant_print_branding"
down_revision: str | None = "0010_unique_return_credit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.add_column(sa.Column("business_display_name", sa.String(160)))
        batch.add_column(sa.Column("business_address", sa.Text()))
        batch.add_column(sa.Column("business_contact", sa.String(240)))
        batch.add_column(sa.Column("logo_url", sa.String(500)))
        batch.add_column(sa.Column("invoice_footer", sa.String(500)))
        batch.add_column(sa.Column("receipt_footer", sa.String(500)))
        batch.add_column(sa.Column("business_registration", sa.String(120)))
        batch.add_column(sa.Column("tax_registration", sa.String(120)))


def downgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        for name in (
            "tax_registration",
            "business_registration",
            "receipt_footer",
            "invoice_footer",
            "logo_url",
            "business_contact",
            "business_address",
            "business_display_name",
        ):
            batch.drop_column(name)
