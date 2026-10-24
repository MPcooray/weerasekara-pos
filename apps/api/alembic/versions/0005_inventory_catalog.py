"""Add products, suppliers, locations, balances and immutable stock ledger."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_inventory_catalog"
down_revision: str | None = "0004_valid_admin_email"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps():
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    ]


def upgrade() -> None:
    category = sa.Enum(
        "SPECTACLE_FRAME",
        "SUNGLASSES",
        "PRESCRIPTION_LENS",
        "CONTACT_LENS",
        "ACCESSORY",
        "OPTICAL_SERVICE",
        name="productcategory",
    )
    movement = sa.Enum(
        "OPENING_STOCK",
        "STOCK_RECEIVED",
        "MANUAL_ADJUSTMENT",
        "DAMAGED_STOCK",
        "SUPPLIER_RETURN",
        "CUSTOMER_RETURN",
        "SALE_DEDUCTION",
        "SALE_REVERSAL",
        name="movementtype",
    )
    op.create_table(
        "suppliers",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("business_name", sa.String(160), nullable=False),
        sa.Column("contact_person", sa.String(160)),
        sa.Column("telephone", sa.String(24)),
        sa.Column("email", sa.String(320)),
        sa.Column("address", sa.String(500)),
        sa.Column("notes", sa.Text()),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "products",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid()),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("barcode", sa.String(64)),
        sa.Column("category", category, nullable=False),
        sa.Column("brand", sa.String(100)),
        sa.Column("model", sa.String(100)),
        sa.Column("description", sa.Text()),
        sa.Column("cost_price_minor", sa.Integer(), nullable=False),
        sa.Column("selling_price_minor", sa.Integer(), nullable=False),
        sa.Column("tax_rate", sa.Integer(), nullable=False),
        sa.Column("tax_inclusive", sa.Boolean(), nullable=False),
        sa.Column("track_stock", sa.Boolean(), nullable=False),
        sa.Column("reorder_threshold", sa.Integer(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("frame_material", sa.String(80)),
        sa.Column("frame_color", sa.String(80)),
        sa.Column("frame_shape", sa.String(80)),
        sa.Column("frame_size", sa.String(40)),
        sa.Column("bridge_size", sa.String(40)),
        sa.Column("temple_length", sa.String(40)),
        sa.Column("frame_style", sa.String(80)),
        sa.Column("lens_type", sa.String(80)),
        sa.Column("lens_material", sa.String(80)),
        sa.Column("refractive_index", sa.String(20)),
        sa.Column("coating_type", sa.String(100)),
        sa.Column("tint", sa.String(80)),
        sa.Column("made_to_order", sa.Boolean(), nullable=False),
        sa.Column("contact_power", sa.Numeric(5, 2)),
        sa.Column("base_curve", sa.Numeric(4, 2)),
        sa.Column("diameter", sa.Numeric(4, 2)),
        sa.Column("pack_size", sa.Integer()),
        sa.Column("expiry_date", sa.Date()),
        *timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "sku", name="uq_products_tenant_sku"),
        sa.UniqueConstraint("tenant_id", "barcode", name="uq_products_tenant_barcode"),
    )
    op.create_table(
        "inventory_locations",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_locations_tenant_code"),
    )
    op.create_table(
        "inventory_balances",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["inventory_locations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "product_id", "location_id", name="uq_balance_product_location"
        ),
    )
    op.create_table(
        "stock_movements",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("movement_type", movement, nullable=False),
        sa.Column("reason", sa.String(500)),
        sa.Column("reference", sa.String(120)),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["inventory_locations.id"]),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for table, columns in {
        "suppliers": ("tenant_id", "business_name", "is_archived"),
        "products": (
            "tenant_id",
            "supplier_id",
            "name",
            "sku",
            "barcode",
            "category",
            "brand",
            "is_archived",
        ),
        "inventory_locations": ("tenant_id",),
        "inventory_balances": ("tenant_id", "product_id", "location_id"),
        "stock_movements": (
            "tenant_id",
            "product_id",
            "location_id",
            "movement_type",
            "actor_id",
            "reference",
            "created_at",
        ),
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    for table in (
        "stock_movements",
        "inventory_balances",
        "inventory_locations",
        "products",
        "suppliers",
    ):
        op.drop_table(table)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="movementtype").drop(bind, checkfirst=True)
        sa.Enum(name="productcategory").drop(bind, checkfirst=True)
