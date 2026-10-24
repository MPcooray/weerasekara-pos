"""quotation return credit and refund workflows

Revision ID: 0009_financial_adjustments
Revises: 0008_payment_timestamps
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009_financial_adjustments"
down_revision: str | None = "0008_payment_timestamps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    refund_status = postgresql.ENUM("RECORDED", name="refundstatus", create_type=False)
    if op.get_bind().dialect.name == "postgresql":
        refund_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "financial_document_sequences",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_type", sa.String(30), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("tenant_id", "document_type", "year"),
    )
    with op.batch_alter_table("invoices") as batch:
        batch.drop_constraint("ck_invoice_balance_equation", type_="check")
        batch.add_column(
            sa.Column("credited_minor", sa.Integer(), server_default="0", nullable=False)
        )
        batch.add_column(
            sa.Column("refunded_minor", sa.Integer(), server_default="0", nullable=False)
        )
        batch.add_column(
            sa.Column("refundable_minor", sa.Integer(), server_default="0", nullable=False)
        )
        batch.create_check_constraint(
            "ck_invoice_credit_balance_equation",
            "paid_minor - refunded_minor + outstanding_minor + credited_minor = "
            "total_minor + refundable_minor",
        )
        batch.create_check_constraint(
            "ck_invoice_adjustments_nonnegative",
            "credited_minor >= 0 AND refunded_minor >= 0 AND refundable_minor >= 0",
        )
    with op.batch_alter_table("quotations") as batch:
        batch.add_column(sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("notes", sa.Text(), nullable=True))
    with op.batch_alter_table("credit_note_lines") as batch:
        batch.add_column(sa.Column("quantity", sa.Integer(), server_default="1", nullable=False))
        batch.add_column(
            sa.Column("subtotal_minor", sa.Integer(), server_default="0", nullable=False)
        )
        batch.add_column(
            sa.Column("discount_minor", sa.Integer(), server_default="0", nullable=False)
        )
        batch.add_column(sa.Column("tax_minor", sa.Integer(), server_default="0", nullable=False))
    with op.batch_alter_table("stock_movements") as batch:
        batch.add_column(sa.Column("return_id", sa.Uuid(), nullable=True))
        batch.create_index("ix_stock_movements_return_id", ["return_id"])
        batch.create_foreign_key("fk_stock_movements_return_id", "returns", ["return_id"], ["id"])
    op.create_table(
        "refunds",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("credit_note_id", sa.Uuid(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column(
            "method",
            postgresql.ENUM(
                "CASH", "CARD", "BANK_TRANSFER", name="paymentmethod", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("reference", sa.String(120), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("status", refund_status, nullable=False),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("amount_minor > 0", name="ck_refund_positive"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["credit_note_id"], ["credit_notes.id"]),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("tenant_id", "invoice_id", "credit_note_id"):
        op.create_index(f"ix_refunds_{column}", "refunds", [column])
    op.create_table(
        "refund_allocations",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("refund_id", sa.Uuid(), nullable=False),
        sa.Column("credit_note_id", sa.Uuid(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["refund_id"], ["refunds.id"]),
        sa.ForeignKeyConstraint(["credit_note_id"], ["credit_notes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refund_id", "credit_note_id", name="uq_refund_credit_allocation"),
    )
    for column in ("tenant_id", "refund_id", "credit_note_id"):
        op.create_index(f"ix_refund_allocations_{column}", "refund_allocations", [column])


def downgrade() -> None:
    op.drop_table("refund_allocations")
    op.drop_table("refunds")
    if op.get_bind().dialect.name == "postgresql":
        postgresql.ENUM("RECORDED", name="refundstatus").drop(op.get_bind(), checkfirst=True)
    with op.batch_alter_table("stock_movements") as batch:
        batch.drop_constraint("fk_stock_movements_return_id", type_="foreignkey")
        batch.drop_index("ix_stock_movements_return_id")
        batch.drop_column("return_id")
    with op.batch_alter_table("credit_note_lines") as batch:
        for column in ("tax_minor", "discount_minor", "subtotal_minor", "quantity"):
            batch.drop_column(column)
    with op.batch_alter_table("quotations") as batch:
        batch.drop_column("notes")
        batch.drop_column("issued_at")
    with op.batch_alter_table("invoices") as batch:
        batch.drop_constraint("ck_invoice_adjustments_nonnegative", type_="check")
        batch.drop_constraint("ck_invoice_credit_balance_equation", type_="check")
        for column in ("refundable_minor", "refunded_minor", "credited_minor"):
            batch.drop_column(column)
        batch.create_check_constraint(
            "ck_invoice_balance_equation", "paid_minor + outstanding_minor = total_minor"
        )
    op.drop_table("financial_document_sequences")
