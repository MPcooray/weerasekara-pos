from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import func, or_, select

from app.api.dependencies import CurrentUser, DbSession
from app.core.permissions import (
    ORDER_COLLECTION_ROLES,
    ORDER_QUALITY_ROLES,
    ORDER_SUPPLIER_ROLES,
    ORDER_WRITE_ROLES,
    Permission,
    has_permission,
)
from app.core.time import colombo_today
from app.models.customer import Customer
from app.models.finance import Invoice
from app.models.order import OpticalOrder, OpticalOrderStatus
from app.schemas.orders import (
    CollectionInput,
    CollectionResponse,
    EventResponse,
    OrderCreate,
    OrderPage,
    OrderResponse,
    OrderUpdate,
    QualityCheckInput,
    QualityCheckResponse,
    StaffOption,
    SupplierTrackingInput,
    SupplierTrackingResponse,
    TransitionRequest,
)
from app.services.orders import (
    collect_order,
    create_order,
    load_order,
    record_quality_check,
    save_supplier_tracking,
    transition_order,
    update_order,
)

router = APIRouter(prefix="/orders", tags=["optical-orders"])


@router.get("/staff/options", response_model=list[StaffOption])
def staff_options(user: CurrentUser, db: DbSession):
    from app.models.user import User

    staff = db.scalars(
        select(User)
        .where(User.tenant_id == user.tenant_id, User.is_active.is_(True))
        .order_by(User.full_name)
    ).all()
    return [
        StaffOption(id=item.id, full_name=item.full_name, role=item.role.value) for item in staff
    ]


def response(db: DbSession, item: OpticalOrder, user) -> OrderResponse:
    can_view_finance = has_permission(user, Permission.INVOICES_VIEW)
    can_view_supplier = has_permission(user, Permission.SUPPLIERS_VIEW)
    outstanding = (
        db.scalar(
            select(Invoice.outstanding_minor).where(
                Invoice.id == item.invoice_id, Invoice.tenant_id == item.tenant_id
            )
        )
        if item.invoice_id and can_view_finance
        else None
    )
    supplier = item.supplier_order
    quality = item.quality_check
    collection = item.collection
    return OrderResponse(
        id=item.id,
        order_number=item.order_number,
        customer_id=item.customer_id,
        visit_id=item.visit_id,
        examination_id=item.examination_id,
        invoice_id=item.invoice_id,
        frame_product_id=item.frame_product_id,
        assigned_staff_id=item.assigned_staff_id,
        status=item.status.value,
        expected_collection_date=item.expected_collection_date,
        overdue=bool(
            item.expected_collection_date
            and item.expected_collection_date < colombo_today()
            and item.status not in {OpticalOrderStatus.COLLECTED, OpticalOrderStatus.CANCELLED}
        ),
        outstanding_minor=outstanding if can_view_finance else None,
        frame_snapshot=item.frame_snapshot,
        prescription_snapshot=item.prescription_snapshot,
        lens_type=item.lens_type,
        lens_material=item.lens_material,
        refractive_index=item.refractive_index,
        coatings=item.coatings or [],
        tint=item.tint,
        right_lens_details=item.right_lens_details,
        left_lens_details=item.left_lens_details,
        fitting_instructions=item.fitting_instructions,
        internal_notes=item.internal_notes,
        created_at=item.created_at,
        updated_at=item.updated_at,
        version=item.version,
        events=[
            EventResponse(
                id=x.id,
                from_status=x.from_status.value if x.from_status else None,
                to_status=x.to_status.value,
                actor_id=x.actor_id,
                reason=x.reason,
                created_at=x.created_at,
            )
            for x in item.events
        ],
        supplier_order=SupplierTrackingResponse(
            id=supplier.id,
            supplier_id=supplier.supplier_id,
            supplier_reference=supplier.supplier_reference,
            ordered_on=supplier.ordered_on,
            expected_delivery=supplier.expected_delivery,
            received_on=supplier.received_on,
            status=supplier.status.value,
            notes=supplier.notes,
            version=supplier.version,
        )
        if supplier and can_view_supplier
        else None,
        quality_check=QualityCheckResponse(
            id=quality.id,
            prescription_verified=quality.prescription_verified,
            lenses_inspected=quality.lenses_inspected,
            frame_inspected=quality.frame_inspected,
            fitting_confirmed=quality.fitting_confirmed,
            remarks=quality.remarks,
            actor_id=quality.actor_id,
            checked_at=quality.checked_at,
        )
        if quality
        else None,
        collection=CollectionResponse(
            id=collection.id,
            actor_id=collection.actor_id,
            collected_at=collection.collected_at,
            notes=collection.notes,
            outstanding_minor_at_collection=(
                collection.outstanding_minor_at_collection if can_view_finance else None
            ),
            outstanding_override=collection.outstanding_override if can_view_finance else None,
        )
        if collection
        else None,
    )


@router.post("", response_model=OrderResponse, status_code=201)
def create(
    data: OrderCreate,
    user: CurrentUser,
    db: DbSession,
    key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)],
):
    if user.role not in ORDER_WRITE_ROLES:
        raise HTTPException(403, "Order permission required")
    try:
        item = create_order(db, user, data, key)
        db.commit()
        return response(db, load_order(db, user.tenant_id, item.id), user)
    except HTTPException:
        db.rollback()
        raise


@router.get("", response_model=OrderPage)
def directory(
    user: CurrentUser,
    db: DbSession,
    search: str = Query("", max_length=100),
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    overdue: bool = False,
    ready: bool = False,
    assigned_staff_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conditions = [OpticalOrder.tenant_id == user.tenant_id]
    statement = select(OpticalOrder).join(Customer, Customer.id == OpticalOrder.customer_id)
    count_statement = (
        select(func.count())
        .select_from(OpticalOrder)
        .join(Customer, Customer.id == OpticalOrder.customer_id)
    )
    if search.strip():
        conditions.append(
            or_(
                OpticalOrder.order_number.ilike(f"%{search.strip()}%"),
                Customer.full_name.ilike(f"%{search.strip()}%"),
                Customer.mobile_number.ilike(f"%{search.strip()}%"),
            )
        )
    if status:
        conditions.append(OpticalOrder.status == status)
    if date_from:
        conditions.append(OpticalOrder.expected_collection_date >= date_from)
    if date_to:
        conditions.append(OpticalOrder.expected_collection_date <= date_to)
    if overdue:
        conditions.extend(
            [
                OpticalOrder.expected_collection_date < colombo_today(),
                OpticalOrder.status.notin_(
                    [OpticalOrderStatus.COLLECTED, OpticalOrderStatus.CANCELLED]
                ),
            ]
        )
    if ready:
        conditions.append(OpticalOrder.status == OpticalOrderStatus.READY_FOR_COLLECTION)
    if assigned_staff_id:
        conditions.append(OpticalOrder.assigned_staff_id == assigned_staff_id)
    total = db.scalar(count_statement.where(*conditions)) or 0
    items = db.scalars(
        statement.where(*conditions)
        .order_by(OpticalOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return OrderPage(
        items=[response(db, load_order(db, user.tenant_id, x.id), user) for x in items],
        page=page,
        page_size=page_size,
        total=total,
        pages=max(1, (total + page_size - 1) // page_size),
    )


@router.get("/{order_id}", response_model=OrderResponse)
def detail(order_id: UUID, user: CurrentUser, db: DbSession):
    return response(db, load_order(db, user.tenant_id, order_id), user)


@router.put("/{order_id}", response_model=OrderResponse)
def edit(order_id: UUID, data: OrderUpdate, user: CurrentUser, db: DbSession):
    if user.role not in ORDER_WRITE_ROLES:
        raise HTTPException(403, "Order permission required")
    try:
        item = update_order(db, user, load_order(db, user.tenant_id, order_id, lock=True), data)
        db.commit()
        return response(db, load_order(db, user.tenant_id, item.id), user)
    except HTTPException:
        db.rollback()
        raise


@router.post("/{order_id}/transitions", response_model=OrderResponse)
def transition(
    order_id: UUID,
    data: TransitionRequest,
    user: CurrentUser,
    db: DbSession,
    key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)],
):
    if user.role not in ORDER_WRITE_ROLES:
        raise HTTPException(403, "Order permission required")
    try:
        item = transition_order(db, user, order_id, data, key)
        db.commit()
        return response(db, load_order(db, user.tenant_id, item.id), user)
    except HTTPException:
        db.rollback()
        raise


@router.put("/{order_id}/supplier", response_model=SupplierTrackingResponse)
def supplier(order_id: UUID, data: SupplierTrackingInput, user: CurrentUser, db: DbSession):
    if user.role not in ORDER_SUPPLIER_ROLES:
        raise HTTPException(403, "Supplier tracking permission required")
    try:
        record = save_supplier_tracking(db, user, load_order(db, user.tenant_id, order_id), data)
        db.commit()
        db.refresh(record)
        return SupplierTrackingResponse(
            id=record.id,
            supplier_id=record.supplier_id,
            supplier_reference=record.supplier_reference,
            ordered_on=record.ordered_on,
            expected_delivery=record.expected_delivery,
            received_on=record.received_on,
            status=record.status.value,
            notes=record.notes,
            version=record.version,
        )
    except HTTPException:
        db.rollback()
        raise


@router.post("/{order_id}/quality-check", response_model=QualityCheckResponse, status_code=201)
def quality(order_id: UUID, data: QualityCheckInput, user: CurrentUser, db: DbSession):
    if user.role not in ORDER_QUALITY_ROLES:
        raise HTTPException(403, "Quality check permission required")
    try:
        check = record_quality_check(db, user, load_order(db, user.tenant_id, order_id), data)
        db.commit()
        db.refresh(check)
        return QualityCheckResponse(
            id=check.id,
            prescription_verified=check.prescription_verified,
            lenses_inspected=check.lenses_inspected,
            frame_inspected=check.frame_inspected,
            fitting_confirmed=check.fitting_confirmed,
            remarks=check.remarks,
            actor_id=check.actor_id,
            checked_at=check.checked_at,
        )
    except HTTPException:
        db.rollback()
        raise


@router.post("/{order_id}/collect", response_model=OrderResponse)
def collect(
    order_id: UUID,
    data: CollectionInput,
    user: CurrentUser,
    db: DbSession,
    key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)],
):
    if user.role not in ORDER_COLLECTION_ROLES:
        raise HTTPException(403, "Collection permission required")
    try:
        item = collect_order(db, user, order_id, data, key)
        db.commit()
        return response(db, load_order(db, user.tenant_id, item.id), user)
    except HTTPException:
        db.rollback()
        raise
