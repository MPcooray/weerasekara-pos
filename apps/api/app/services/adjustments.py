import hashlib
import json
from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.finance import (
    CreditNote,
    CreditNoteLine,
    CreditNoteStatus,
    FinancialIdempotency,
    IdempotencyStatus,
    Invoice,
    InvoiceStatus,
    Quotation,
    QuotationLine,
    QuotationStatus,
    Refund,
    RefundAllocation,
    RefundStatus,
    Return,
    ReturnLine,
    ReturnStatus,
)
from app.models.inventory import InventoryBalance, MovementType, StockMovement
from app.models.product import Product, ProductCategory
from app.models.user import User
from app.schemas.adjustments import QuotationCreate, RefundCreate, ReturnCreate
from app.schemas.checkout import CheckoutLineInput, CheckoutRequest
from app.services.audit import record_audit
from app.services.checkout import calculate_checkout, confirm_checkout, validate_references
from app.services.document_numbering import next_document_number
from app.services.financial_calculations import (
    CalculationLine,
    calculate_totals,
    round_ratio_half_up,
)


def _hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def claim(
    db: Session, user: User, operation: str, key: str, payload: dict
) -> tuple[FinancialIdempotency, UUID | None]:
    digest = _hash(payload)
    existing = db.scalar(
        select(FinancialIdempotency).where(
            FinancialIdempotency.tenant_id == user.tenant_id,
            FinancialIdempotency.operation == operation,
            FinancialIdempotency.idempotency_key == key,
        )
    )
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(409, "Idempotency key was used with a different request")
        if existing.status == IdempotencyStatus.COMPLETED and existing.resource_id:
            return existing, existing.resource_id
        raise HTTPException(409, "This request is already in progress")
    item = FinancialIdempotency(
        tenant_id=user.tenant_id,
        operation=operation,
        idempotency_key=key,
        request_hash=digest,
        status=IdempotencyStatus.IN_PROGRESS,
    )
    try:
        with db.begin_nested():
            db.add(item)
            db.flush()
    except IntegrityError as exc:
        existing = db.scalar(
            select(FinancialIdempotency).where(
                FinancialIdempotency.tenant_id == user.tenant_id,
                FinancialIdempotency.operation == operation,
                FinancialIdempotency.idempotency_key == key,
            )
        )
        if (
            existing
            and existing.request_hash == digest
            and existing.status == IdempotencyStatus.COMPLETED
        ):
            return existing, existing.resource_id
        raise HTTPException(409, "This request conflicts with an existing operation") from exc
    return item, None


def complete(claim_record: FinancialIdempotency, resource_type: str, resource_id: UUID) -> None:
    claim_record.status = IdempotencyStatus.COMPLETED
    claim_record.resource_type = resource_type
    claim_record.resource_id = resource_id
    claim_record.completed_at = datetime.now(UTC)


def calculate_quotation(db: Session, user: User, data: QuotationCreate):
    validate_references(
        db,
        user,
        CheckoutRequest(
            customer_id=data.customer_id,
            examination_id=data.examination_id,
            lines=[
                CheckoutLineInput(
                    product_id=x.product_id,
                    quantity=x.quantity,
                    line_discount_minor=x.line_discount_minor,
                )
                for x in data.lines
            ],
        ),
    )
    if len({x.product_id for x in data.lines}) != len(data.lines):
        raise HTTPException(422, "Each product may appear only once")
    products = {
        p.id: p
        for p in db.scalars(
            select(Product).where(
                Product.tenant_id == user.tenant_id,
                Product.id.in_([x.product_id for x in data.lines]),
                Product.is_archived.is_(False),
            )
        ).all()
    }
    if len(products) != len(data.lines):
        raise HTTPException(404, "One or more products were not found")
    totals = calculate_totals(
        [
            CalculationLine(
                x.quantity,
                products[x.product_id].selling_price_minor,
                x.line_discount_minor,
                products[x.product_id].tax_rate,
                products[x.product_id].tax_exempt,
                products[x.product_id].tax_inclusive,
            )
            for x in data.lines
        ],
        invoice_discount_minor=data.invoice_discount_minor,
    )
    return products, totals


def save_quotation(
    db: Session, user: User, data: QuotationCreate, quotation: Quotation | None = None
) -> Quotation:
    products, totals = calculate_quotation(db, user, data)
    if quotation is None:
        now = datetime.now(UTC)
        quotation = Quotation(
            tenant_id=user.tenant_id,
            quotation_number=next_document_number(db, user.tenant_id, "quotation", now.year),
            actor_id=user.id,
            status=QuotationStatus.DRAFT,
            subtotal_minor=0,
            discount_minor=0,
            tax_minor=0,
            total_minor=0,
        )
        db.add(quotation)
        db.flush()
    elif quotation.status != QuotationStatus.DRAFT:
        raise HTTPException(409, "Only draft quotations can be edited")
    quotation.customer_id = data.customer_id
    quotation.examination_id = data.examination_id
    quotation.expires_on = data.expires_on
    quotation.notes = data.notes
    quotation.subtotal_minor = totals.subtotal_minor
    quotation.discount_minor = totals.discount_minor
    quotation.tax_minor = totals.tax_minor
    quotation.total_minor = totals.total_minor
    quotation.lines.clear()
    db.flush()
    for source, calc in zip(data.lines, totals.lines, strict=True):
        product = products[source.product_id]
        quotation.lines.append(
            QuotationLine(
                tenant_id=user.tenant_id,
                product_id=product.id,
                product_name=product.name,
                sku=product.sku,
                quantity=source.quantity,
                unit_price_minor=product.selling_price_minor,
                line_discount_minor=calc.line_discount_minor,
                invoice_discount_minor=calc.invoice_discount_minor,
                tax_rate_bps=product.tax_rate,
                tax_exempt=product.tax_exempt,
                tax_inclusive=product.tax_inclusive,
                tax_minor=calc.tax_minor,
                line_total_minor=calc.total_minor,
            )
        )
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="quotation.saved",
        entity_type="quotation",
        entity_id=quotation.id,
    )
    db.flush()
    return quotation


def issue_quotation(db: Session, user: User, quotation_id: UUID, key: str) -> Quotation:
    idem, resource = claim(db, user, "quotation.issue", key, {"quotation_id": quotation_id})
    if resource:
        return db.get(Quotation, resource)
    quotation = db.scalar(
        select(Quotation)
        .where(Quotation.id == quotation_id, Quotation.tenant_id == user.tenant_id)
        .with_for_update()
    )
    if not quotation:
        raise HTTPException(404, "Quotation not found")
    if quotation.status != QuotationStatus.DRAFT:
        raise HTTPException(409, "Only draft quotations can be issued")
    quotation.status = QuotationStatus.ISSUED
    quotation.issued_at = datetime.now(UTC)
    complete(idem, "quotation", quotation.id)
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="quotation.issued",
        entity_type="quotation",
        entity_id=quotation.id,
    )
    db.flush()
    return quotation


def conversion_preview(db: Session, user: User, quotation: Quotation):
    request = CheckoutRequest(
        customer_id=quotation.customer_id,
        examination_id=quotation.examination_id,
        invoice_discount_minor=sum(x.invoice_discount_minor for x in quotation.lines),
        lines=[
            CheckoutLineInput(
                product_id=x.product_id,
                quantity=x.quantity,
                line_discount_minor=x.line_discount_minor,
            )
            for x in quotation.lines
        ],
    )
    *_, totals, current = calculate_checkout(db, user, request)
    differences = []
    for quoted, fresh in zip(quotation.lines, current, strict=True):
        if quoted.unit_price_minor != fresh.unit_price_minor:
            differences.append(f"Price changed for {quoted.product_name}")
        if quoted.line_total_minor != fresh.line_total_minor:
            differences.append(f"Total changed for {quoted.product_name}")
    if quotation.total_minor != totals.total_minor:
        differences.append("Quotation total changed")
    return request, totals.total_minor, differences


def convert_quotation(
    db: Session, user: User, quotation_id: UUID, approve_changes: bool, key: str
) -> Invoice:
    idem, resource = claim(
        db,
        user,
        "quotation.convert",
        key,
        {"quotation_id": quotation_id, "approve_changes": approve_changes},
    )
    if resource:
        return db.get(Invoice, resource)
    quotation = db.scalar(
        select(Quotation)
        .where(Quotation.id == quotation_id, Quotation.tenant_id == user.tenant_id)
        .options(selectinload(Quotation.lines))
        .with_for_update()
    )
    if not quotation:
        raise HTTPException(404, "Quotation not found")
    if quotation.status == QuotationStatus.CONVERTED and quotation.converted_invoice_id:
        complete(idem, "invoice", quotation.converted_invoice_id)
        return db.get(Invoice, quotation.converted_invoice_id)
    if quotation.status != QuotationStatus.ISSUED:
        raise HTTPException(409, "Only issued quotations can be converted")
    if quotation.expires_on and quotation.expires_on < date.today():
        quotation.status = QuotationStatus.EXPIRED
        raise HTTPException(409, "Quotation has expired")
    request, _, differences = conversion_preview(db, user, quotation)
    if differences and not approve_changes:
        raise HTTPException(
            409,
            detail={"message": "Current values differ from quotation", "differences": differences},
        )
    invoice = confirm_checkout(db, user, request, f"quotation:{quotation.id}:{key}")
    quotation.status = QuotationStatus.CONVERTED
    quotation.converted_invoice_id = invoice.id
    complete(idem, "invoice", invoice.id)
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="quotation.converted",
        entity_type="quotation",
        entity_id=quotation.id,
    )
    db.flush()
    return invoice


def request_return(
    db: Session, user: User, invoice_id: UUID, data: ReturnCreate, key: str
) -> Return:
    idem, resource = claim(
        db, user, "return.request", key, {"invoice_id": invoice_id, **data.model_dump(mode="json")}
    )
    if resource:
        return db.get(Return, resource)
    invoice = db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
        .options(selectinload(Invoice.lines))
        .with_for_update()
    )
    if not invoice or invoice.status not in {
        InvoiceStatus.FINALIZED,
        InvoiceStatus.PARTIALLY_PAID,
        InvoiceStatus.PAID,
    }:
        raise HTTPException(409 if invoice else 404, "Invoice is not eligible for return")
    sold = {x.id: x for x in invoice.lines}
    requested = {x.invoice_line_id: x for x in data.lines}
    if len(requested) != len(data.lines) or any(x not in sold for x in requested):
        raise HTTPException(422, "Invalid or duplicate invoice line")
    previous = dict(
        db.execute(
            select(ReturnLine.invoice_line_id, func.coalesce(func.sum(ReturnLine.quantity), 0))
            .join(Return)
            .where(Return.invoice_id == invoice.id, Return.status != ReturnStatus.CANCELLED)
            .group_by(ReturnLine.invoice_line_id)
        ).all()
    )
    for line_id, item in requested.items():
        if previous.get(line_id, 0) + item.quantity > sold[line_id].quantity:
            raise HTTPException(409, "Return quantity exceeds remaining sold quantity")
    now = datetime.now(UTC)
    record = Return(
        tenant_id=user.tenant_id,
        invoice_id=invoice.id,
        return_number=next_document_number(db, user.tenant_id, "return", now.year),
        status=ReturnStatus.DRAFT,
        reason=data.reason,
        actor_id=user.id,
        total_minor=0,
    )
    db.add(record)
    db.flush()
    total = 0
    for item in data.lines:
        line = sold[item.invoice_line_id]
        amount = round_ratio_half_up(line.line_total_minor * item.quantity, line.quantity)
        total += amount
        record.lines.append(
            ReturnLine(
                tenant_id=user.tenant_id,
                invoice_line_id=line.id,
                quantity=item.quantity,
                amount_minor=amount,
                restock=item.restock,
            )
        )
    record.total_minor = total
    complete(idem, "return", record.id)
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="return.requested",
        entity_type="return",
        entity_id=record.id,
    )
    db.flush()
    return record


def approve_return(db: Session, user: User, return_id: UUID, key: str) -> tuple[Return, CreditNote]:
    idem, resource = claim(db, user, "return.approve", key, {"return_id": return_id})
    if resource:
        credit = db.get(CreditNote, resource)
        return db.get(Return, credit.return_id), credit
    record = db.scalar(
        select(Return)
        .where(Return.id == return_id, Return.tenant_id == user.tenant_id)
        .options(selectinload(Return.lines))
        .with_for_update()
    )
    if not record:
        raise HTTPException(404, "Return not found")
    if record.status != ReturnStatus.DRAFT:
        raise HTTPException(409, "Only requested returns can be approved")
    invoice = db.scalar(
        select(Invoice)
        .where(Invoice.id == record.invoice_id, Invoice.tenant_id == user.tenant_id)
        .options(selectinload(Invoice.lines))
        .with_for_update()
    )
    invoice_lines = {x.id: x for x in invoice.lines}
    now = datetime.now(UTC)
    credit = CreditNote(
        tenant_id=user.tenant_id,
        invoice_id=invoice.id,
        return_id=record.id,
        credit_note_number=next_document_number(db, user.tenant_id, "credit_note", now.year),
        status=CreditNoteStatus.DRAFT,
        reason=record.reason,
        total_minor=record.total_minor,
        actor_id=user.id,
        issued_at=now,
    )
    db.add(credit)
    db.flush()
    for item in record.lines:
        line = invoice_lines[item.invoice_line_id]
        subtotal = line.unit_price_minor * item.quantity
        line_discount = round_ratio_half_up(
            (line.line_discount_minor + line.invoice_discount_minor) * item.quantity, line.quantity
        )
        tax = round_ratio_half_up(line.tax_minor * item.quantity, line.quantity)
        credit.lines.append(
            CreditNoteLine(
                tenant_id=user.tenant_id,
                invoice_line_id=line.id,
                description=line.product_name,
                quantity=item.quantity,
                subtotal_minor=subtotal,
                discount_minor=line_discount,
                tax_minor=tax,
                amount_minor=item.amount_minor,
            )
        )
        product = db.get(Product, line.product_id) if line.product_id else None
        may_restock = (
            item.restock
            and product
            and product.track_stock
            and not product.made_to_order
            and product.category != ProductCategory.OPTICAL_SERVICE
        )
        if may_restock:
            balance = db.scalar(
                select(InventoryBalance)
                .where(
                    InventoryBalance.tenant_id == user.tenant_id,
                    InventoryBalance.location_id == invoice.location_id,
                    InventoryBalance.product_id == product.id,
                )
                .with_for_update()
            )
            if not balance:
                raise HTTPException(409, "Inventory balance is unavailable for restocking")
            balance.quantity += item.quantity
            balance.version += 1
            db.add(
                StockMovement(
                    tenant_id=user.tenant_id,
                    product_id=product.id,
                    location_id=invoice.location_id,
                    quantity_delta=item.quantity,
                    movement_type=MovementType.CUSTOMER_RETURN,
                    reason=record.reason,
                    reference=record.return_number,
                    invoice_id=invoice.id,
                    return_id=record.id,
                    actor_id=user.id,
                    balance_after=balance.quantity,
                )
            )
    prior_outstanding = invoice.outstanding_minor
    invoice.credited_minor += credit.total_minor
    invoice.outstanding_minor = max(
        0,
        invoice.total_minor
        - invoice.credited_minor
        - (invoice.paid_minor - invoice.refunded_minor),
    )
    invoice.refundable_minor += max(0, credit.total_minor - prior_outstanding)
    invoice.status = (
        InvoiceStatus.PAID if invoice.outstanding_minor == 0 else InvoiceStatus.PARTIALLY_PAID
    )
    record.status = ReturnStatus.FINALIZED
    record.finalized_at = now
    credit.status = CreditNoteStatus.ISSUED
    complete(idem, "credit_note", credit.id)
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="return.approved",
        entity_type="return",
        entity_id=record.id,
    )
    db.flush()
    return record, credit


def record_refund(
    db: Session, user: User, credit_note_id: UUID, data: RefundCreate, key: str
) -> Refund:
    idem, resource = claim(
        db,
        user,
        "refund.record",
        key,
        {"credit_note_id": credit_note_id, **data.model_dump(mode="json")},
    )
    if resource:
        return db.get(Refund, resource)
    credit = db.scalar(
        select(CreditNote)
        .where(
            CreditNote.id == credit_note_id,
            CreditNote.tenant_id == user.tenant_id,
            CreditNote.status == CreditNoteStatus.ISSUED,
        )
        .with_for_update()
    )
    if not credit:
        raise HTTPException(404, "Credit note not found")
    invoice = db.scalar(
        select(Invoice)
        .where(Invoice.id == credit.invoice_id, Invoice.tenant_id == user.tenant_id)
        .with_for_update()
    )
    already = (
        db.scalar(
            select(func.coalesce(func.sum(Refund.amount_minor), 0)).where(
                Refund.credit_note_id == credit.id, Refund.tenant_id == user.tenant_id
            )
        )
        or 0
    )
    available = min(invoice.refundable_minor, credit.total_minor - already)
    if data.amount_minor > available:
        raise HTTPException(409, "Refund exceeds the currently refundable credit")
    now = datetime.now(UTC)
    refund = Refund(
        tenant_id=user.tenant_id,
        invoice_id=invoice.id,
        credit_note_id=credit.id,
        amount_minor=data.amount_minor,
        method=data.method,
        reason=data.reason,
        reference=data.reference,
        actor_id=user.id,
        status=RefundStatus.RECORDED,
        refunded_at=now,
        created_at=now,
    )
    db.add(refund)
    db.flush()
    db.add(
        RefundAllocation(
            tenant_id=user.tenant_id,
            refund_id=refund.id,
            credit_note_id=credit.id,
            amount_minor=data.amount_minor,
        )
    )
    invoice.refunded_minor += data.amount_minor
    invoice.refundable_minor -= data.amount_minor
    complete(idem, "refund", refund.id)
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="refund.recorded",
        entity_type="refund",
        entity_id=refund.id,
    )
    db.flush()
    return refund
