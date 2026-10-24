import enum
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import IdMixin, TimestampMixin


class MovementType(str, enum.Enum):
    OPENING_STOCK = "opening_stock"
    STOCK_RECEIVED = "stock_received"
    MANUAL_ADJUSTMENT = "manual_adjustment"
    DAMAGED_STOCK = "damaged_stock"
    SUPPLIER_RETURN = "supplier_return"
    CUSTOMER_RETURN = "customer_return"
    SALE_DEDUCTION = "sale_deduction"
    SALE_REVERSAL = "sale_reversal"


class InventoryLocation(IdMixin, TimestampMixin, Base):
    __tablename__ = "inventory_locations"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_locations_tenant_code"),)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(40))
    is_default: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)


class InventoryBalance(IdMixin, TimestampMixin, Base):
    __tablename__ = "inventory_balances"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "product_id", "location_id", name="uq_balance_product_location"
        ),
    )
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"), index=True)
    location_id: Mapped[UUID] = mapped_column(ForeignKey("inventory_locations.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)


class StockMovement(IdMixin, Base):
    __tablename__ = "stock_movements"
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"), index=True)
    location_id: Mapped[UUID] = mapped_column(ForeignKey("inventory_locations.id"), index=True)
    quantity_delta: Mapped[int] = mapped_column(Integer)
    movement_type: Mapped[MovementType] = mapped_column(Enum(MovementType), index=True)
    reason: Mapped[str | None] = mapped_column(String(500))
    reference: Mapped[str | None] = mapped_column(String(120), index=True)
    invoice_id: Mapped[UUID | None] = mapped_column(ForeignKey("invoices.id"), index=True)
    return_id: Mapped[UUID | None] = mapped_column(ForeignKey("returns.id"), index=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    balance_after: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
