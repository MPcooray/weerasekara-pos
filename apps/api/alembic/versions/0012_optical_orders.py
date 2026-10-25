"""add optical order management

Revision ID: 0012_optical_orders
Revises: 0011_tenant_print_branding
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012_optical_orders"
down_revision: str | None = "0011_tenant_print_branding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORDER_VALUES = (
    "DRAFT",
    "CONFIRMED",
    "AWAITING_LENSES",
    "IN_PREPARATION",
    "QUALITY_CHECK",
    "READY_FOR_COLLECTION",
    "COLLECTED",
    "CANCELLED",
)
SUPPLIER_VALUES = ("NOT_ORDERED", "ORDERED", "SHIPPED", "RECEIVED", "CANCELLED")


def enum_type(name: str, values: tuple[str, ...]):
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.ENUM(*values, name=name, create_type=False)
    return sa.Enum(*values, name=name)


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        postgresql.ENUM(*ORDER_VALUES, name="opticalorderstatus").create(
            op.get_bind(), checkfirst=True
        )
        postgresql.ENUM(*SUPPLIER_VALUES, name="supplierorderstatus").create(
            op.get_bind(), checkfirst=True
        )
    order_status = enum_type("opticalorderstatus", ORDER_VALUES)
    supplier_status = enum_type("supplierorderstatus", SUPPLIER_VALUES)
    op.create_table(
        "optical_orders",
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("order_number", sa.String(32), nullable=False),
        sa.Column("creation_key", sa.String(100), nullable=False),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("visit_id", sa.Uuid(), sa.ForeignKey("visits.id")),
        sa.Column("examination_id", sa.Uuid(), sa.ForeignKey("examinations.id"), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), sa.ForeignKey("invoices.id")),
        sa.Column("frame_product_id", sa.Uuid(), sa.ForeignKey("products.id")),
        sa.Column("assigned_staff_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", order_status, nullable=False),
        sa.Column("expected_collection_date", sa.Date()),
        sa.Column("frame_snapshot", sa.JSON()),
        sa.Column("prescription_snapshot", sa.JSON(), nullable=False),
        sa.Column("lens_type", sa.String(100), nullable=False),
        sa.Column("lens_material", sa.String(100)),
        sa.Column("refractive_index", sa.String(30)),
        sa.Column("coatings", sa.JSON(), nullable=False),
        sa.Column("tint", sa.String(100)),
        sa.Column("right_lens_details", sa.Text()),
        sa.Column("left_lens_details", sa.Text()),
        sa.Column("fitting_instructions", sa.Text()),
        sa.Column("internal_notes", sa.Text()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("ready_at", sa.DateTime(timezone=True)),
        sa.Column("collected_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("tenant_id", "order_number", name="uq_optical_orders_tenant_number"),
        sa.UniqueConstraint("tenant_id", "creation_key", name="uq_optical_orders_creation_key"),
    )
    for column in (
        "tenant_id",
        "order_number",
        "customer_id",
        "visit_id",
        "examination_id",
        "invoice_id",
        "frame_product_id",
        "assigned_staff_id",
        "status",
        "expected_collection_date",
    ):
        op.create_index(f"ix_optical_orders_{column}", "optical_orders", [column])
    op.create_table(
        "optical_order_events",
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("optical_orders.id"), nullable=False),
        sa.Column("from_status", order_status),
        sa.Column("to_status", order_status, nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
    )
    op.create_index("ix_optical_order_events_tenant_id", "optical_order_events", ["tenant_id"])
    op.create_index("ix_optical_order_events_order_id", "optical_order_events", ["order_id"])
    op.create_index("ix_optical_order_events_created_at", "optical_order_events", ["created_at"])
    op.create_table(
        "lens_supplier_orders",
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("optical_orders.id"), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("supplier_reference", sa.String(120)),
        sa.Column("ordered_on", sa.Date()),
        sa.Column("expected_delivery", sa.Date()),
        sa.Column("received_on", sa.Date()),
        sa.Column("status", supplier_status, nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("updated_by_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("order_id", name="uq_lens_supplier_order"),
    )
    for column in ("tenant_id", "order_id", "supplier_id", "status"):
        op.create_index(f"ix_lens_supplier_orders_{column}", "lens_supplier_orders", [column])
    op.create_table(
        "order_quality_checks",
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("optical_orders.id"), nullable=False),
        sa.Column("prescription_verified", sa.Boolean(), nullable=False),
        sa.Column("lenses_inspected", sa.Boolean(), nullable=False),
        sa.Column("frame_inspected", sa.Boolean(), nullable=False),
        sa.Column("fitting_confirmed", sa.Boolean(), nullable=False),
        sa.Column("remarks", sa.Text()),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.UniqueConstraint("order_id", name="uq_order_quality_check"),
    )
    op.create_index("ix_order_quality_checks_tenant_id", "order_quality_checks", ["tenant_id"])
    op.create_index("ix_order_quality_checks_order_id", "order_quality_checks", ["order_id"])
    op.create_table(
        "order_collections",
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("optical_orders.id"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("outstanding_minor_at_collection", sa.Integer(), nullable=False),
        sa.Column("outstanding_override", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.UniqueConstraint("order_id", name="uq_order_collection"),
    )
    op.create_index("ix_order_collections_tenant_id", "order_collections", ["tenant_id"])
    op.create_index("ix_order_collections_order_id", "order_collections", ["order_id"])
    op.create_table(
        "order_idempotency",
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("operation", sa.String(50), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.UniqueConstraint(
            "tenant_id", "operation", "idempotency_key", name="uq_order_idempotency"
        ),
    )
    op.create_index("ix_order_idempotency_tenant_id", "order_idempotency", ["tenant_id"])


def downgrade() -> None:
    for table in (
        "order_idempotency",
        "order_collections",
        "order_quality_checks",
        "lens_supplier_orders",
        "optical_order_events",
        "optical_orders",
    ):
        op.drop_table(table)
    if op.get_bind().dialect.name == "postgresql":
        postgresql.ENUM(name="supplierorderstatus").drop(op.get_bind(), checkfirst=True)
        postgresql.ENUM(name="opticalorderstatus").drop(op.get_bind(), checkfirst=True)
