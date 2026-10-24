import hashlib
import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.examination import Examination, ExaminationStatus
from app.models.finance import (
    FinancialIdempotency,
    IdempotencyStatus,
    Invoice,
    InvoiceLine,
    InvoiceStatus,
)
from app.models.inventory import InventoryBalance, InventoryLocation, MovementType, StockMovement
from app.models.product import Product
from app.models.user import User
from app.schemas.checkout import CheckoutLineResult, CheckoutPreview, CheckoutRequest
from app.services.audit import record_audit
from app.services.financial_calculations import CalculationLine, calculate_totals
from app.services.invoice_numbering import next_invoice_number


def request_hash(data: CheckoutRequest) -> str:
    canonical = json.dumps(data.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def validate_references(db: Session, user: User, data: CheckoutRequest) -> InventoryLocation:
    location = (
        db.scalar(
            select(InventoryLocation).where(
                InventoryLocation.tenant_id == user.tenant_id,
                InventoryLocation.id == data.location_id,
                InventoryLocation.is_active.is_(True),
            )
        )
        if data.location_id
        else db.scalar(
            select(InventoryLocation).where(
                InventoryLocation.tenant_id == user.tenant_id,
                InventoryLocation.is_default.is_(True),
                InventoryLocation.is_active.is_(True),
            )
        )
    )
    if location is None:
        raise HTTPException(status_code=422, detail="A valid inventory location is required")
    if (
        data.customer_id
        and db.scalar(
            select(Customer.id).where(
                Customer.id == data.customer_id,
                Customer.tenant_id == user.tenant_id,
                Customer.is_archived.is_(False),
            )
        )
        is None
    ):
        raise HTTPException(status_code=404, detail="Customer not found")
    if data.examination_id:
        examination = db.scalar(
            select(Examination).where(
                Examination.id == data.examination_id,
                Examination.tenant_id == user.tenant_id,
                Examination.status == ExaminationStatus.FINALIZED,
            )
        )
        if examination is None or (
            data.customer_id is not None and examination.customer_id != data.customer_id
        ):
            raise HTTPException(
                status_code=422,
                detail="Finalized prescription does not belong to the selected customer",
            )
        if data.customer_id is None:
            raise HTTPException(
                status_code=422, detail="A customer is required when associating a prescription"
            )
    return location


def calculate_checkout(db: Session, user: User, data: CheckoutRequest, *, lock: bool = False):
    if len({line.product_id for line in data.lines}) != len(data.lines):
        raise HTTPException(status_code=422, detail="Each product may appear only once in the cart")
    location = validate_references(db, user, data)
    query = (
        select(Product)
        .where(
            Product.tenant_id == user.tenant_id,
            Product.id.in_(sorted((line.product_id for line in data.lines), key=str)),
        )
        .order_by(Product.id)
    )
    if lock:
        query = query.with_for_update()
    products = {p.id: p for p in db.scalars(query).all()}
    if len(products) != len(data.lines):
        raise HTTPException(status_code=404, detail="One or more products were not found")
    balances = {}
    tracked_ids = sorted(
        (p.id for p in products.values() if p.track_stock and not p.made_to_order), key=str
    )
    if tracked_ids:
        balance_query = (
            select(InventoryBalance)
            .where(
                InventoryBalance.tenant_id == user.tenant_id,
                InventoryBalance.location_id == location.id,
                InventoryBalance.product_id.in_(tracked_ids),
            )
            .order_by(InventoryBalance.product_id)
        )
        if lock:
            balance_query = balance_query.with_for_update()
        balances = {b.product_id: b for b in db.scalars(balance_query).all()}
    calculations = []
    ordered = []
    for item in data.lines:
        product = products[item.product_id]
        if product.is_archived:
            raise HTTPException(status_code=409, detail=f"{product.name} is archived")
        if (
            item.expected_unit_price_minor is not None
            and item.expected_unit_price_minor != product.selling_price_minor
        ):
            raise HTTPException(
                status_code=409, detail=f"Price changed for {product.name}; refresh the cart"
            )
        available = (
            balances.get(product.id).quantity
            if product.id in balances
            else (0 if product.track_stock and not product.made_to_order else None)
        )
        if available is not None and available < item.quantity:
            raise HTTPException(
                status_code=409,
                detail=f"Insufficient stock for {product.name}; {available} available",
            )
        calculations.append(
            CalculationLine(
                item.quantity,
                product.selling_price_minor,
                item.line_discount_minor,
                product.tax_rate,
                product.tax_exempt,
                product.tax_inclusive,
            )
        )
        ordered.append((item, product, available))
    try:
        totals = calculate_totals(calculations, invoice_discount_minor=data.invoice_discount_minor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    lines = [
        CheckoutLineResult(
            product_id=p.id,
            product_name=p.name,
            sku=p.sku,
            quantity=item.quantity,
            unit_price_minor=p.selling_price_minor,
            line_discount_minor=calc.line_discount_minor,
            invoice_discount_minor=calc.invoice_discount_minor,
            tax_rate_bps=p.tax_rate,
            tax_exempt=p.tax_exempt,
            tax_inclusive=p.tax_inclusive,
            tax_minor=calc.tax_minor,
            line_total_minor=calc.total_minor,
            stock_available=available,
        )
        for (item, p, available), calc in zip(ordered, totals.lines, strict=True)
    ]
    return location, products, balances, totals, lines


def preview_checkout(db: Session, user: User, data: CheckoutRequest) -> CheckoutPreview:
    *_, totals, lines = calculate_checkout(db, user, data)
    return CheckoutPreview(
        lines=lines,
        subtotal_minor=totals.subtotal_minor,
        discount_minor=totals.discount_minor,
        tax_minor=totals.tax_minor,
        total_minor=totals.total_minor,
        outstanding_minor=totals.total_minor,
    )


def confirm_checkout(db: Session, user: User, data: CheckoutRequest, key: str) -> Invoice:
    digest = request_hash(data)
    existing = db.scalar(
        select(FinancialIdempotency).where(
            FinancialIdempotency.tenant_id == user.tenant_id,
            FinancialIdempotency.operation == "checkout",
            FinancialIdempotency.idempotency_key == key,
        )
    )
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(
                status_code=409, detail="Idempotency key was already used with a different checkout"
            )
        if existing.status == IdempotencyStatus.COMPLETED and existing.resource_id:
            return db.scalar(
                select(Invoice).where(
                    Invoice.id == existing.resource_id, Invoice.tenant_id == user.tenant_id
                )
            )
        raise HTTPException(
            status_code=409, detail="Checkout with this idempotency key is already in progress"
        )
    claim = FinancialIdempotency(
        tenant_id=user.tenant_id,
        operation="checkout",
        idempotency_key=key,
        request_hash=digest,
        status=IdempotencyStatus.IN_PROGRESS,
    )
    try:
        with db.begin_nested():
            db.add(claim)
            db.flush()
    except IntegrityError as exc:
        existing = db.scalar(
            select(FinancialIdempotency).where(
                FinancialIdempotency.tenant_id == user.tenant_id,
                FinancialIdempotency.operation == "checkout",
                FinancialIdempotency.idempotency_key == key,
            )
        )
        if (
            existing
            and existing.request_hash == digest
            and existing.status == IdempotencyStatus.COMPLETED
            and existing.resource_id
        ):
            return db.get(Invoice, existing.resource_id)
        if existing and existing.request_hash != digest:
            raise HTTPException(
                status_code=409, detail="Idempotency key was already used with a different checkout"
            ) from exc
        raise HTTPException(
            status_code=409, detail="Checkout with this idempotency key is already in progress"
        ) from exc
    location, _, balances, totals, lines = calculate_checkout(db, user, data, lock=True)
    now = datetime.now(UTC)
    number = next_invoice_number(db, user.tenant_id, now.year)
    invoice = Invoice(
        tenant_id=user.tenant_id,
        location_id=location.id,
        invoice_number=number,
        customer_id=data.customer_id,
        examination_id=data.examination_id,
        actor_id=user.id,
        status=InvoiceStatus.FINALIZED,
        invoice_at=now,
        subtotal_minor=totals.subtotal_minor,
        discount_minor=totals.discount_minor,
        tax_minor=totals.tax_minor,
        total_minor=totals.total_minor,
        paid_minor=0,
        outstanding_minor=totals.total_minor,
        notes=data.notes,
        finalized_at=now,
    )
    db.add(invoice)
    db.flush()
    for source, result in zip(data.lines, lines, strict=True):
        db.add(
            InvoiceLine(
                tenant_id=user.tenant_id,
                invoice_id=invoice.id,
                product_id=result.product_id,
                product_name=result.product_name,
                sku=result.sku,
                quantity=result.quantity,
                unit_price_minor=result.unit_price_minor,
                line_discount_minor=result.line_discount_minor,
                invoice_discount_minor=result.invoice_discount_minor,
                tax_rate_bps=result.tax_rate_bps,
                tax_exempt=result.tax_exempt,
                tax_inclusive=result.tax_inclusive,
                tax_minor=result.tax_minor,
                line_total_minor=result.line_total_minor,
            )
        )
        balance = balances.get(result.product_id)
        if balance:
            balance.quantity -= source.quantity
            balance.version += 1
            db.add(
                StockMovement(
                    tenant_id=user.tenant_id,
                    product_id=result.product_id,
                    location_id=location.id,
                    quantity_delta=-source.quantity,
                    movement_type=MovementType.SALE_DEDUCTION,
                    reason="Invoice sale",
                    reference=number,
                    invoice_id=invoice.id,
                    actor_id=user.id,
                    balance_after=balance.quantity,
                )
            )
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="invoice.finalized",
        entity_type="invoice",
        entity_id=invoice.id,
    )
    claim.status = IdempotencyStatus.COMPLETED
    claim.resource_type = "invoice"
    claim.resource_id = invoice.id
    claim.completed_at = now
    db.flush()
    return invoice
