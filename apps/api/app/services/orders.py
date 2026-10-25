from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.customer import Customer
from app.models.examination import Examination, ExaminationStatus
from app.models.finance import Invoice
from app.models.order import (
    LensSupplierOrder,
    OpticalOrder,
    OpticalOrderEvent,
    OpticalOrderStatus,
    OrderCollection,
    OrderIdempotency,
    OrderQualityCheck,
)
from app.models.product import Product, ProductCategory
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.models.visit import Visit
from app.schemas.orders import (
    CollectionInput,
    OrderCreate,
    QualityCheckInput,
    SupplierTrackingInput,
    TransitionRequest,
)
from app.services.audit import record_audit
from app.services.document_numbering import next_document_number

TRANSITIONS = {
    OpticalOrderStatus.DRAFT: {OpticalOrderStatus.CONFIRMED, OpticalOrderStatus.CANCELLED},
    OpticalOrderStatus.CONFIRMED: {
        OpticalOrderStatus.AWAITING_LENSES,
        OpticalOrderStatus.IN_PREPARATION,
        OpticalOrderStatus.CANCELLED,
    },
    OpticalOrderStatus.AWAITING_LENSES: {
        OpticalOrderStatus.IN_PREPARATION,
        OpticalOrderStatus.CANCELLED,
    },
    OpticalOrderStatus.IN_PREPARATION: {
        OpticalOrderStatus.QUALITY_CHECK,
        OpticalOrderStatus.CANCELLED,
    },
    OpticalOrderStatus.QUALITY_CHECK: {
        OpticalOrderStatus.READY_FOR_COLLECTION,
        OpticalOrderStatus.IN_PREPARATION,
        OpticalOrderStatus.CANCELLED,
    },
    OpticalOrderStatus.READY_FOR_COLLECTION: {
        OpticalOrderStatus.COLLECTED,
        OpticalOrderStatus.CANCELLED,
    },
    OpticalOrderStatus.COLLECTED: set(),
    OpticalOrderStatus.CANCELLED: set(),
}


def _json_value(value):
    if isinstance(value, (Decimal, date, datetime)):
        return value.isoformat() if hasattr(value, "isoformat") else str(value)
    return value


def prescription_snapshot(exam: Examination) -> dict:
    fields = (
        "examination_number",
        "examined_at",
        "prescription_type",
        "expires_on",
        "od_sphere",
        "od_cylinder",
        "od_axis",
        "od_add",
        "od_distance_va",
        "od_near_va",
        "od_prism",
        "od_prism_base",
        "od_notes",
        "os_sphere",
        "os_cylinder",
        "os_axis",
        "os_add",
        "os_distance_va",
        "os_near_va",
        "os_prism",
        "os_prism_base",
        "os_notes",
        "pd_binocular",
        "pd_right",
        "pd_left",
        "notes",
    )
    result = {}
    for field in fields:
        value = getattr(exam, field)
        if hasattr(value, "value"):
            value = value.value
        result[field] = _json_value(value)
    return result


def frame_snapshot(product: Product | None, details: str | None) -> dict | None:
    if not product and not details:
        return None
    return {
        "product_id": str(product.id) if product else None,
        "name": product.name if product else None,
        "sku": product.sku if product else None,
        "brand": product.brand if product else None,
        "model": product.model if product else None,
        "color": product.frame_color if product else None,
        "size": product.frame_size if product else None,
        "details": details,
    }


def load_order(db: Session, tenant_id: UUID, order_id: UUID, *, lock: bool = False) -> OpticalOrder:
    statement = (
        select(OpticalOrder)
        .where(OpticalOrder.id == order_id, OpticalOrder.tenant_id == tenant_id)
        .options(
            selectinload(OpticalOrder.events),
            selectinload(OpticalOrder.supplier_order),
            selectinload(OpticalOrder.quality_check),
            selectinload(OpticalOrder.collection),
        )
        .execution_options(populate_existing=True)
    )
    if lock:
        statement = statement.with_for_update()
    item = db.scalar(statement)
    if not item:
        raise HTTPException(404, "Optical order not found")
    return item


def validate_refs(db: Session, user: User, data: OrderCreate):
    customer = db.scalar(
        select(Customer).where(
            Customer.id == data.customer_id, Customer.tenant_id == user.tenant_id
        )
    )
    exam = db.scalar(
        select(Examination).where(
            Examination.id == data.examination_id, Examination.tenant_id == user.tenant_id
        )
    )
    if (
        not customer
        or not exam
        or exam.customer_id != customer.id
        or exam.status != ExaminationStatus.FINALIZED
    ):
        raise HTTPException(422, "A finalized prescription belonging to the customer is required")
    if data.visit_id and not db.scalar(
        select(Visit.id).where(
            Visit.id == data.visit_id,
            Visit.customer_id == customer.id,
            Visit.tenant_id == user.tenant_id,
        )
    ):
        raise HTTPException(422, "Visit does not belong to this customer")
    invoice = None
    if data.invoice_id:
        invoice = db.scalar(
            select(Invoice).where(
                Invoice.id == data.invoice_id, Invoice.tenant_id == user.tenant_id
            )
        )
        if not invoice or invoice.customer_id != customer.id or invoice.examination_id != exam.id:
            raise HTTPException(422, "Invoice must belong to the same customer and prescription")
    frame = None
    if data.frame_product_id:
        frame = db.scalar(
            select(Product).where(
                Product.id == data.frame_product_id, Product.tenant_id == user.tenant_id
            )
        )
        if not frame or frame.category not in {
            ProductCategory.SPECTACLE_FRAME,
            ProductCategory.SUNGLASSES,
        }:
            raise HTTPException(422, "Frame product is invalid")
    if data.assigned_staff_id and not db.scalar(
        select(User.id).where(
            User.id == data.assigned_staff_id,
            User.tenant_id == user.tenant_id,
            User.is_active.is_(True),
        )
    ):
        raise HTTPException(422, "Assigned staff member is invalid")
    return exam, frame


def create_order(db: Session, user: User, data: OrderCreate, key: str) -> OpticalOrder:
    existing = db.scalar(
        select(OpticalOrder).where(
            OpticalOrder.tenant_id == user.tenant_id, OpticalOrder.creation_key == key
        )
    )
    if existing:
        return existing
    exam, frame = validate_refs(db, user, data)
    now = datetime.now(UTC)
    item = OpticalOrder(
        tenant_id=user.tenant_id,
        order_number=next_document_number(db, user.tenant_id, "optical_order", now.year),
        creation_key=key,
        customer_id=data.customer_id,
        visit_id=data.visit_id,
        examination_id=data.examination_id,
        invoice_id=data.invoice_id,
        frame_product_id=data.frame_product_id,
        assigned_staff_id=data.assigned_staff_id,
        created_by_id=user.id,
        status=OpticalOrderStatus.DRAFT,
        expected_collection_date=data.expected_collection_date,
        frame_snapshot=frame_snapshot(frame, data.frame_details),
        prescription_snapshot=prescription_snapshot(exam),
        lens_type=data.lens_type,
        lens_material=data.lens_material,
        refractive_index=data.refractive_index,
        coatings=data.coatings,
        tint=data.tint,
        right_lens_details=data.right_lens_details,
        left_lens_details=data.left_lens_details,
        fitting_instructions=data.fitting_instructions,
        internal_notes=data.internal_notes,
    )
    db.add(item)
    db.flush()
    db.add(
        OpticalOrderEvent(
            tenant_id=user.tenant_id,
            order_id=item.id,
            from_status=None,
            to_status=OpticalOrderStatus.DRAFT,
            actor_id=user.id,
            reason="Order created",
            created_at=now,
        )
    )
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="optical_order.created",
        entity_type="optical_order",
        entity_id=item.id,
    )
    return item


def update_order(db: Session, user: User, item: OpticalOrder, data) -> OpticalOrder:
    if item.status != OpticalOrderStatus.DRAFT:
        raise HTTPException(409, "Only draft orders can be edited")
    if item.version != data.expected_version:
        raise HTTPException(409, "Order was updated by another user")
    exam, frame = validate_refs(db, user, data)
    for field in (
        "customer_id",
        "visit_id",
        "examination_id",
        "invoice_id",
        "frame_product_id",
        "assigned_staff_id",
        "expected_collection_date",
        "lens_type",
        "lens_material",
        "refractive_index",
        "coatings",
        "tint",
        "right_lens_details",
        "left_lens_details",
        "fitting_instructions",
        "internal_notes",
    ):
        setattr(item, field, getattr(data, field))
    item.frame_snapshot = frame_snapshot(frame, data.frame_details)
    item.prescription_snapshot = prescription_snapshot(exam)
    item.version += 1
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="optical_order.updated",
        entity_type="optical_order",
        entity_id=item.id,
    )
    return item


def _idempotent(db: Session, tenant_id: UUID, operation: str, key: str, order_id: UUID) -> bool:
    found = db.scalar(
        select(OrderIdempotency).where(
            OrderIdempotency.tenant_id == tenant_id,
            OrderIdempotency.operation == operation,
            OrderIdempotency.idempotency_key == key,
        )
    )
    if found:
        if found.resource_id != order_id:
            raise HTTPException(409, "Idempotency key already used")
        return True
    db.add(
        OrderIdempotency(
            tenant_id=tenant_id,
            operation=operation,
            idempotency_key=key,
            resource_id=order_id,
            created_at=datetime.now(UTC),
        )
    )
    return False


def transition_order(
    db: Session, user: User, order_id: UUID, data: TransitionRequest, key: str
) -> OpticalOrder:
    item = load_order(db, user.tenant_id, order_id, lock=True)
    if _idempotent(db, user.tenant_id, "transition", key, item.id):
        return item
    if item.version != data.expected_version:
        raise HTTPException(409, "Order was updated by another user")
    if data.status == OpticalOrderStatus.COLLECTED:
        raise HTTPException(409, "Use the collection workflow to collect an order")
    if data.status not in TRANSITIONS[item.status]:
        raise HTTPException(
            409, f"Cannot move order from {item.status.value} to {data.status.value}"
        )
    if data.status == OpticalOrderStatus.CANCELLED and user.role not in {
        UserRole.OWNER,
        UserRole.MANAGER,
    }:
        raise HTTPException(403, "Only owners and managers can cancel orders")
    if data.status == OpticalOrderStatus.READY_FOR_COLLECTION:
        qc = item.quality_check
        if not qc or not all(
            (
                qc.prescription_verified,
                qc.lenses_inspected,
                qc.frame_inspected,
                qc.fitting_confirmed,
            )
        ):
            raise HTTPException(409, "All quality checks are required before collection readiness")
    now = datetime.now(UTC)
    old = item.status
    item.status = data.status
    item.version += 1
    if data.status == OpticalOrderStatus.CONFIRMED:
        item.confirmed_at = now
    if data.status == OpticalOrderStatus.READY_FOR_COLLECTION:
        item.ready_at = now
    if data.status == OpticalOrderStatus.CANCELLED:
        item.cancelled_at = now
    db.add(
        OpticalOrderEvent(
            tenant_id=user.tenant_id,
            order_id=item.id,
            from_status=old,
            to_status=data.status,
            actor_id=user.id,
            reason=data.reason,
            created_at=now,
        )
    )
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action=f"optical_order.{data.status.value}",
        entity_type="optical_order",
        entity_id=item.id,
    )
    return item


def save_supplier_tracking(
    db: Session, user: User, item: OpticalOrder, data: SupplierTrackingInput
):
    supplier = db.scalar(
        select(Supplier).where(
            Supplier.id == data.supplier_id,
            Supplier.tenant_id == user.tenant_id,
            Supplier.is_archived.is_(False),
        )
    )
    if not supplier:
        raise HTTPException(422, "Supplier not found")
    record = item.supplier_order
    if record and data.expected_version != record.version:
        raise HTTPException(409, "Supplier tracking was updated by another user")
    if not record:
        record = LensSupplierOrder(tenant_id=user.tenant_id, order_id=item.id, version=1)
        db.add(record)
    else:
        record.version += 1
    for field in (
        "supplier_id",
        "supplier_reference",
        "ordered_on",
        "expected_delivery",
        "received_on",
        "status",
        "notes",
    ):
        setattr(record, field, getattr(data, field))
    record.updated_by_id = user.id
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="optical_order.supplier_updated",
        entity_type="optical_order",
        entity_id=item.id,
    )
    return record


def record_quality_check(db: Session, user: User, item: OpticalOrder, data: QualityCheckInput):
    if item.status != OpticalOrderStatus.QUALITY_CHECK:
        raise HTTPException(409, "Order must be in quality check status")
    if item.quality_check:
        raise HTTPException(409, "Quality check is already recorded")
    if not all(
        (
            data.prescription_verified,
            data.lenses_inspected,
            data.frame_inspected,
            data.fitting_confirmed,
        )
    ):
        raise HTTPException(422, "All required quality checks must be completed")
    check = OrderQualityCheck(
        tenant_id=user.tenant_id,
        order_id=item.id,
        actor_id=user.id,
        checked_at=datetime.now(UTC),
        **data.model_dump(),
    )
    db.add(check)
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="optical_order.quality_checked",
        entity_type="optical_order",
        entity_id=item.id,
    )
    return check


def collect_order(
    db: Session, user: User, order_id: UUID, data: CollectionInput, key: str
) -> OpticalOrder:
    item = load_order(db, user.tenant_id, order_id, lock=True)
    if _idempotent(db, user.tenant_id, "collection", key, item.id):
        return item
    if item.version != data.expected_version:
        raise HTTPException(409, "Order was updated by another user")
    if item.status != OpticalOrderStatus.READY_FOR_COLLECTION:
        raise HTTPException(409, "Only ready orders can be collected")
    outstanding = 0
    if item.invoice_id:
        invoice = db.scalar(
            select(Invoice)
            .where(Invoice.id == item.invoice_id, Invoice.tenant_id == user.tenant_id)
            .with_for_update()
        )
        outstanding = invoice.outstanding_minor
    if outstanding and not data.allow_outstanding_balance:
        raise HTTPException(
            409, "Invoice has an outstanding balance; explicit authorized override is required"
        )
    if outstanding and user.role not in {UserRole.OWNER, UserRole.MANAGER}:
        raise HTTPException(
            403, "Only owners and managers may authorize collection with an outstanding balance"
        )
    now = datetime.now(UTC)
    old = item.status
    item.status = OpticalOrderStatus.COLLECTED
    item.collected_at = now
    item.version += 1
    db.add(
        OrderCollection(
            tenant_id=user.tenant_id,
            order_id=item.id,
            actor_id=user.id,
            collected_at=now,
            notes=data.notes,
            outstanding_minor_at_collection=outstanding,
            outstanding_override=bool(outstanding),
        )
    )
    db.add(
        OpticalOrderEvent(
            tenant_id=user.tenant_id,
            order_id=item.id,
            from_status=old,
            to_status=OpticalOrderStatus.COLLECTED,
            actor_id=user.id,
            reason=data.notes,
            created_at=now,
        )
    )
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="optical_order.collected",
        entity_type="optical_order",
        entity_id=item.id,
    )
    return item
