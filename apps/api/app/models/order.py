import enum
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    inspect,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import IdMixin, TimestampMixin


class OpticalOrderStatus(str, enum.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    AWAITING_LENSES = "awaiting_lenses"
    IN_PREPARATION = "in_preparation"
    QUALITY_CHECK = "quality_check"
    READY_FOR_COLLECTION = "ready_for_collection"
    COLLECTED = "collected"
    CANCELLED = "cancelled"


class SupplierOrderStatus(str, enum.Enum):
    NOT_ORDERED = "not_ordered"
    ORDERED = "ordered"
    SHIPPED = "shipped"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class OpticalOrder(IdMixin, TimestampMixin, Base):
    __tablename__ = "optical_orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "order_number", name="uq_optical_orders_tenant_number"),
        UniqueConstraint("tenant_id", "creation_key", name="uq_optical_orders_creation_key"),
    )
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    order_number: Mapped[str] = mapped_column(String(32), index=True)
    creation_key: Mapped[str] = mapped_column(String(100))
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    visit_id: Mapped[UUID | None] = mapped_column(ForeignKey("visits.id"), index=True)
    examination_id: Mapped[UUID] = mapped_column(ForeignKey("examinations.id"), index=True)
    invoice_id: Mapped[UUID | None] = mapped_column(ForeignKey("invoices.id"), index=True)
    frame_product_id: Mapped[UUID | None] = mapped_column(ForeignKey("products.id"), index=True)
    assigned_staff_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[OpticalOrderStatus] = mapped_column(Enum(OpticalOrderStatus), index=True)
    expected_collection_date: Mapped[date | None] = mapped_column(Date, index=True)
    frame_snapshot: Mapped[dict | None] = mapped_column(JSON)
    prescription_snapshot: Mapped[dict] = mapped_column(JSON)
    lens_type: Mapped[str] = mapped_column(String(100))
    lens_material: Mapped[str | None] = mapped_column(String(100))
    refractive_index: Mapped[str | None] = mapped_column(String(30))
    coatings: Mapped[list] = mapped_column(JSON, default=list)
    tint: Mapped[str | None] = mapped_column(String(100))
    right_lens_details: Mapped[str | None] = mapped_column(Text)
    left_lens_details: Mapped[str | None] = mapped_column(Text)
    fitting_instructions: Mapped[str | None] = mapped_column(Text)
    internal_notes: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    events: Mapped[list["OpticalOrderEvent"]] = relationship(
        back_populates="order", order_by="OpticalOrderEvent.created_at"
    )
    supplier_order: Mapped["LensSupplierOrder | None"] = relationship(
        back_populates="order", uselist=False
    )
    quality_check: Mapped["OrderQualityCheck | None"] = relationship(
        back_populates="order", uselist=False
    )
    collection: Mapped["OrderCollection | None"] = relationship(
        back_populates="order", uselist=False
    )


class OpticalOrderEvent(IdMixin, Base):
    __tablename__ = "optical_order_events"
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("optical_orders.id"), index=True)
    from_status: Mapped[OpticalOrderStatus | None] = mapped_column(Enum(OpticalOrderStatus))
    to_status: Mapped[OpticalOrderStatus] = mapped_column(Enum(OpticalOrderStatus))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    order: Mapped[OpticalOrder] = relationship(back_populates="events")


class LensSupplierOrder(IdMixin, TimestampMixin, Base):
    __tablename__ = "lens_supplier_orders"
    __table_args__ = (UniqueConstraint("order_id", name="uq_lens_supplier_order"),)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("optical_orders.id"), index=True)
    supplier_id: Mapped[UUID] = mapped_column(ForeignKey("suppliers.id"), index=True)
    supplier_reference: Mapped[str | None] = mapped_column(String(120))
    ordered_on: Mapped[date | None] = mapped_column(Date)
    expected_delivery: Mapped[date | None] = mapped_column(Date)
    received_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[SupplierOrderStatus] = mapped_column(Enum(SupplierOrderStatus), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    updated_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    order: Mapped[OpticalOrder] = relationship(back_populates="supplier_order")


class OrderQualityCheck(IdMixin, Base):
    __tablename__ = "order_quality_checks"
    __table_args__ = (UniqueConstraint("order_id", name="uq_order_quality_check"),)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("optical_orders.id"), index=True)
    prescription_verified: Mapped[bool] = mapped_column(Boolean)
    lenses_inspected: Mapped[bool] = mapped_column(Boolean)
    frame_inspected: Mapped[bool] = mapped_column(Boolean)
    fitting_confirmed: Mapped[bool] = mapped_column(Boolean)
    remarks: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    order: Mapped[OpticalOrder] = relationship(back_populates="quality_check")


class OrderCollection(IdMixin, Base):
    __tablename__ = "order_collections"
    __table_args__ = (UniqueConstraint("order_id", name="uq_order_collection"),)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("optical_orders.id"), index=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    outstanding_minor_at_collection: Mapped[int] = mapped_column(Integer)
    outstanding_override: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[OpticalOrder] = relationship(back_populates="collection")


class OrderIdempotency(IdMixin, Base):
    __tablename__ = "order_idempotency"
    __table_args__ = (
        UniqueConstraint("tenant_id", "operation", "idempotency_key", name="uq_order_idempotency"),
    )
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    operation: Mapped[str] = mapped_column(String(50))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


ORDER_SPECIFICATION_FIELDS = {
    "tenant_id",
    "customer_id",
    "visit_id",
    "examination_id",
    "invoice_id",
    "frame_product_id",
    "frame_snapshot",
    "prescription_snapshot",
    "lens_type",
    "lens_material",
    "refractive_index",
    "coatings",
    "tint",
    "right_lens_details",
    "left_lens_details",
    "fitting_instructions",
}


@event.listens_for(Session, "before_flush")
def protect_order_history(session: Session, *_args: object) -> None:
    for obj in session.dirty:
        if isinstance(obj, OpticalOrder) and obj.status != OpticalOrderStatus.DRAFT:
            state = inspect(obj)
            if any(state.attrs[name].history.has_changes() for name in ORDER_SPECIFICATION_FIELDS):
                raise ValueError("Confirmed optical order specifications are immutable")
        elif isinstance(obj, (OpticalOrderEvent, OrderQualityCheck, OrderCollection)):
            if any(attr.history.has_changes() for attr in inspect(obj).attrs):
                raise ValueError("Optical order history is immutable")
    for obj in session.deleted:
        if isinstance(
            obj, (OpticalOrderEvent, OrderQualityCheck, OrderCollection, OrderIdempotency)
        ):
            raise ValueError("Optical order history cannot be deleted")
        if isinstance(obj, OpticalOrder) and obj.status != OpticalOrderStatus.DRAFT:
            raise ValueError("Confirmed optical orders cannot be deleted")
