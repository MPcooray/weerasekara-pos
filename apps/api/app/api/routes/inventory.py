import math
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, DbSession
from app.core.permissions import (
    INVENTORY_WRITE_ROLES,
    SUPPLIER_WRITE_ROLES,
    Permission,
    has_permission,
)
from app.models.inventory import InventoryBalance, InventoryLocation, StockMovement
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.inventory import (
    InventorySummary,
    LocationResponse,
    MovementResponse,
    ProductCreate,
    ProductPage,
    ProductResponse,
    ProductUpdate,
    StockMutation,
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)
from app.services.audit import record_audit
from app.services.inventory import default_location, mutate_stock

router = APIRouter(tags=["inventory"])


def require_inventory_write(user: User) -> None:
    if user.role not in INVENTORY_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Inventory management permission required")


def product_for_user(db: DbSession, user: User, product_id: UUID) -> Product:
    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.tenant_id == user.tenant_id)
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def product_response(db: DbSession, user: User, product: Product) -> ProductResponse:
    quantity = (
        db.scalar(
            select(func.coalesce(func.sum(InventoryBalance.quantity), 0)).where(
                InventoryBalance.tenant_id == product.tenant_id,
                InventoryBalance.product_id == product.id,
            )
        )
        or 0
    )
    stock_version = (
        db.scalar(
            select(func.max(InventoryBalance.version)).where(
                InventoryBalance.tenant_id == product.tenant_id,
                InventoryBalance.product_id == product.id,
            )
        )
        or 1
    )
    values = {c.name: getattr(product, c.name) for c in Product.__table__.columns}
    if not has_permission(user, Permission.SUPPLIER_COSTS_VIEW):
        values["cost_price_minor"] = None
        values["supplier_id"] = None
    return ProductResponse.model_validate(
        {
            **values,
            "quantity": quantity,
            "stock_version": stock_version,
        }
    )


def validate_supplier(db: DbSession, user: User, supplier_id: UUID | None) -> None:
    if (
        supplier_id
        and db.scalar(
            select(Supplier.id).where(
                Supplier.id == supplier_id,
                Supplier.tenant_id == user.tenant_id,
                Supplier.is_archived.is_(False),
            )
        )
        is None
    ):
        raise HTTPException(status_code=422, detail="Supplier is invalid")


@router.get("/suppliers", response_model=list[SupplierResponse])
def list_suppliers(user: CurrentUser, db: DbSession, include_archived: bool = False):
    if not has_permission(user, Permission.SUPPLIERS_VIEW):
        raise HTTPException(status_code=403, detail="Supplier access denied")
    query = select(Supplier).where(Supplier.tenant_id == user.tenant_id)
    if not include_archived:
        query = query.where(Supplier.is_archived.is_(False))
    return list(db.scalars(query.order_by(Supplier.business_name)).all())


@router.post("/suppliers", response_model=SupplierResponse, status_code=201)
def create_supplier(data: SupplierCreate, user: CurrentUser, db: DbSession):
    if user.role not in SUPPLIER_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Supplier management permission required")
    supplier = Supplier(**data.model_dump(), tenant_id=user.tenant_id)
    db.add(supplier)
    db.flush()
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="supplier.created",
        entity_type="supplier",
        entity_id=supplier.id,
    )
    db.commit()
    db.refresh(supplier)
    return supplier


@router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
def supplier_detail(supplier_id: UUID, user: CurrentUser, db: DbSession):
    if not has_permission(user, Permission.SUPPLIERS_VIEW):
        raise HTTPException(status_code=403, detail="Supplier access denied")
    item = db.scalar(
        select(Supplier).where(Supplier.id == supplier_id, Supplier.tenant_id == user.tenant_id)
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return item


@router.patch("/suppliers/{supplier_id}", response_model=SupplierResponse)
def update_supplier(supplier_id: UUID, data: SupplierUpdate, user: CurrentUser, db: DbSession):
    if user.role not in SUPPLIER_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Supplier management permission required")
    item = supplier_detail(supplier_id, user, db)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    item.version += 1
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="supplier.updated",
        entity_type="supplier",
        entity_id=item.id,
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/products", response_model=ProductPage)
def list_products(
    user: CurrentUser,
    db: DbSession,
    search: str = Query("", max_length=120),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_archived: bool = False,
):
    conditions = [Product.tenant_id == user.tenant_id]
    if not include_archived:
        conditions.append(Product.is_archived.is_(False))
    if search.strip():
        term = f"%{search.strip()}%"
        conditions.append(
            or_(
                Product.name.ilike(term),
                Product.sku.ilike(term),
                Product.barcode.ilike(term),
                Product.brand.ilike(term),
            )
        )
    total = db.scalar(select(func.count()).select_from(Product).where(*conditions)) or 0
    items = db.scalars(
        select(Product)
        .where(*conditions)
        .order_by(Product.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ProductPage(
        items=[product_response(db, user, p) for p in items],
        page=page,
        page_size=page_size,
        total=total,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.post("/products", response_model=ProductResponse, status_code=201)
def create_product(data: ProductCreate, user: CurrentUser, db: DbSession):
    require_inventory_write(user)
    validate_supplier(db, user, data.supplier_id)
    product = Product(**data.model_dump(), tenant_id=user.tenant_id)
    db.add(product)
    try:
        db.flush()
        default_location(db, user.tenant_id)
        record_audit(
            db,
            tenant_id=user.tenant_id,
            actor_id=user.id,
            action="product.created",
            entity_type="product",
            entity_id=product.id,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="SKU or barcode already exists for this shop"
        ) from exc
    db.refresh(product)
    return product_response(db, user, product)


@router.get("/products/{product_id}", response_model=ProductResponse)
def product_detail(product_id: UUID, user: CurrentUser, db: DbSession):
    return product_response(db, user, product_for_user(db, user, product_id))


@router.patch("/products/{product_id}", response_model=ProductResponse)
def update_product(product_id: UUID, data: ProductUpdate, user: CurrentUser, db: DbSession):
    require_inventory_write(user)
    product = product_for_user(db, user, product_id)
    values = data.model_dump(exclude_unset=True)
    validate_supplier(db, user, values.get("supplier_id"))
    price_changed = any(
        k in values and values[k] != getattr(product, k)
        for k in ("cost_price_minor", "selling_price_minor")
    )
    for key, value in values.items():
        setattr(product, key, value)
    product.version += 1
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="product.price_changed" if price_changed else "product.updated",
        entity_type="product",
        entity_id=product.id,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="SKU or barcode already exists for this shop"
        ) from exc
    db.refresh(product)
    return product_response(db, user, product)


@router.get("/inventory/locations", response_model=list[LocationResponse])
def locations(user: CurrentUser, db: DbSession):
    require_inventory_write(user)
    location = default_location(db, user.tenant_id)
    db.commit()
    return list(
        db.scalars(
            select(InventoryLocation)
            .where(
                InventoryLocation.tenant_id == user.tenant_id, InventoryLocation.is_active.is_(True)
            )
            .order_by(InventoryLocation.name)
        ).all()
    ) or [location]


@router.post("/products/{product_id}/movements", response_model=MovementResponse, status_code=201)
def create_movement(product_id: UUID, data: StockMutation, user: CurrentUser, db: DbSession):
    require_inventory_write(user)
    movement = mutate_stock(
        db, user=user, product=product_for_user(db, user, product_id), data=data
    )
    db.commit()
    db.refresh(movement)
    return movement


@router.get("/products/{product_id}/movements", response_model=list[MovementResponse])
def movements(product_id: UUID, user: CurrentUser, db: DbSession):
    require_inventory_write(user)
    product_for_user(db, user, product_id)
    return list(
        db.scalars(
            select(StockMovement)
            .where(
                StockMovement.tenant_id == user.tenant_id, StockMovement.product_id == product_id
            )
            .order_by(StockMovement.created_at.desc())
        ).all()
    )


@router.get("/inventory/summary", response_model=InventorySummary)
def inventory_summary(user: CurrentUser, db: DbSession):
    products = db.scalars(
        select(Product).where(Product.tenant_id == user.tenant_id, Product.is_archived.is_(False))
    ).all()
    quantities = {
        p.id: db.scalar(
            select(func.coalesce(func.sum(InventoryBalance.quantity), 0)).where(
                InventoryBalance.tenant_id == user.tenant_id, InventoryBalance.product_id == p.id
            )
        )
        or 0
        for p in products
    }
    tracked = [p for p in products if p.track_stock]
    by_category = {}
    for p in products:
        by_category[p.category.value] = by_category.get(p.category.value, 0) + quantities[p.id]
    return InventorySummary(
        active_products=len(products),
        tracked_products=len(tracked),
        total_units=sum(quantities[p.id] for p in tracked),
        low_stock_products=sum(0 < quantities[p.id] <= p.reorder_threshold for p in tracked),
        out_of_stock_products=sum(quantities[p.id] == 0 for p in tracked),
        valuation_minor=(
            sum(quantities[p.id] * p.cost_price_minor for p in tracked)
            if has_permission(user, Permission.SUPPLIER_COSTS_VIEW)
            else None
        ),
        by_category=by_category,
    )
