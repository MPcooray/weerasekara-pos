import enum
from datetime import date
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import IdMixin, TimestampMixin


class ProductCategory(str, enum.Enum):
    SPECTACLE_FRAME = "spectacle_frame"
    SUNGLASSES = "sunglasses"
    PRESCRIPTION_LENS = "prescription_lens"
    CONTACT_LENS = "contact_lens"
    ACCESSORY = "accessory"
    OPTICAL_SERVICE = "optical_service"


class Product(IdMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_products_tenant_sku"),
        UniqueConstraint("tenant_id", "barcode", name="uq_products_tenant_barcode"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    supplier_id: Mapped[UUID | None] = mapped_column(ForeignKey("suppliers.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    sku: Mapped[str] = mapped_column(String(64), index=True)
    barcode: Mapped[str | None] = mapped_column(String(64), index=True)
    category: Mapped[ProductCategory] = mapped_column(Enum(ProductCategory), index=True)
    brand: Mapped[str | None] = mapped_column(String(100), index=True)
    model: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    cost_price_minor: Mapped[int] = mapped_column(Integer)
    selling_price_minor: Mapped[int] = mapped_column(Integer)
    tax_rate: Mapped[int] = mapped_column(Integer, default=0)
    tax_inclusive: Mapped[bool] = mapped_column(Boolean, default=True)
    tax_exempt: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    track_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    reorder_threshold: Mapped[int] = mapped_column(Integer, default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    frame_material: Mapped[str | None] = mapped_column(String(80))
    frame_color: Mapped[str | None] = mapped_column(String(80))
    frame_shape: Mapped[str | None] = mapped_column(String(80))
    frame_size: Mapped[str | None] = mapped_column(String(40))
    bridge_size: Mapped[str | None] = mapped_column(String(40))
    temple_length: Mapped[str | None] = mapped_column(String(40))
    frame_style: Mapped[str | None] = mapped_column(String(80))
    lens_type: Mapped[str | None] = mapped_column(String(80))
    lens_material: Mapped[str | None] = mapped_column(String(80))
    refractive_index: Mapped[str | None] = mapped_column(String(20))
    coating_type: Mapped[str | None] = mapped_column(String(100))
    tint: Mapped[str | None] = mapped_column(String(80))
    made_to_order: Mapped[bool] = mapped_column(Boolean, default=False)
    contact_power: Mapped[float | None] = mapped_column(Numeric(5, 2))
    base_curve: Mapped[float | None] = mapped_column(Numeric(4, 2))
    diameter: Mapped[float | None] = mapped_column(Numeric(4, 2))
    pack_size: Mapped[int | None] = mapped_column(Integer)
    expiry_date: Mapped[date | None] = mapped_column(Date)
