from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.inventory import InventoryBalance, InventoryLocation, StockMovement
from app.models.product import Product
from app.models.user import User
from app.schemas.inventory import StockMutation
from app.services.audit import record_audit


def default_location(db: Session, tenant_id: UUID) -> InventoryLocation:
    location = db.scalar(
        select(InventoryLocation).where(
            InventoryLocation.tenant_id == tenant_id, InventoryLocation.is_default.is_(True)
        )
    )
    if location is None:
        location = InventoryLocation(
            tenant_id=tenant_id, name="Main Store", code="MAIN", is_default=True
        )
        db.add(location)
        db.flush()
    return location


def mutate_stock(
    db: Session, *, user: User, product: Product, data: StockMutation
) -> StockMovement:
    if product.is_archived:
        raise HTTPException(
            status_code=409, detail="Archived products must be reactivated before stock changes"
        )
    if not product.track_stock:
        raise HTTPException(status_code=409, detail="Stock tracking is disabled for this product")
    location = (
        db.scalar(
            select(InventoryLocation).where(
                InventoryLocation.id == data.location_id,
                InventoryLocation.tenant_id == user.tenant_id,
                InventoryLocation.is_active.is_(True),
            )
        )
        if data.location_id
        else default_location(db, user.tenant_id)
    )
    if location is None:
        raise HTTPException(status_code=404, detail="Inventory location not found")
    balance = db.scalar(
        select(InventoryBalance).where(
            InventoryBalance.tenant_id == user.tenant_id,
            InventoryBalance.product_id == product.id,
            InventoryBalance.location_id == location.id,
        )
    )
    if balance is None:
        balance = InventoryBalance(
            tenant_id=user.tenant_id, product_id=product.id, location_id=location.id, quantity=0
        )
        db.add(balance)
        db.flush()
    new_quantity = balance.quantity + data.quantity_delta
    if new_quantity < 0:
        raise HTTPException(
            status_code=409, detail="Insufficient stock; negative inventory is not allowed"
        )
    result = db.execute(
        update(InventoryBalance)
        .where(
            InventoryBalance.id == balance.id,
            InventoryBalance.tenant_id == user.tenant_id,
            InventoryBalance.version == data.expected_version,
        )
        .values(quantity=new_quantity, version=data.expected_version + 1)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Stock changed by another user; refresh and retry"
        )
    movement = StockMovement(
        tenant_id=user.tenant_id,
        product_id=product.id,
        location_id=location.id,
        quantity_delta=data.quantity_delta,
        movement_type=data.movement_type,
        reason=data.reason,
        reference=data.reference,
        actor_id=user.id,
        balance_after=new_quantity,
    )
    db.add(movement)
    db.flush()
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="inventory.stock_changed",
        entity_type="stock_movement",
        entity_id=movement.id,
    )
    return movement
