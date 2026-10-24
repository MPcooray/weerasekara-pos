from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentUser, DbSession
from app.models.finance import Invoice, InvoiceStatus, Payment
from app.models.user import CHECKOUT_ROLES, PAYMENT_WRITE_ROLES
from app.schemas.checkout import (
    CheckoutLineResult,
    CheckoutPreview,
    CheckoutRequest,
    InvoiceDetail,
    InvoicePage,
    InvoiceSummary,
    PaymentCreate,
    PaymentResponse,
    PaymentResult,
)
from app.services.checkout import confirm_checkout, preview_checkout
from app.services.payments import record_payment

router = APIRouter(tags=["checkout"])


def invoice_detail(invoice: Invoice) -> InvoiceDetail:
    return InvoiceDetail(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        customer_id=invoice.customer_id,
        invoice_at=invoice.invoice_at,
        status=invoice.status.value,
        total_minor=invoice.total_minor,
        paid_minor=invoice.paid_minor,
        outstanding_minor=invoice.outstanding_minor,
        location_id=invoice.location_id,
        examination_id=invoice.examination_id,
        actor_id=invoice.actor_id,
        subtotal_minor=invoice.subtotal_minor,
        discount_minor=invoice.discount_minor,
        tax_minor=invoice.tax_minor,
        notes=invoice.notes,
        lines=[
            CheckoutLineResult(
                product_id=line.product_id,
                product_name=line.product_name,
                sku=line.sku,
                quantity=line.quantity,
                unit_price_minor=line.unit_price_minor,
                line_discount_minor=line.line_discount_minor,
                invoice_discount_minor=line.invoice_discount_minor,
                tax_rate_bps=line.tax_rate_bps,
                tax_exempt=line.tax_exempt,
                tax_inclusive=line.tax_inclusive,
                tax_minor=line.tax_minor,
                line_total_minor=line.line_total_minor,
                stock_available=None,
            )
            for line in invoice.lines
        ],
        payments=[payment_response(payment) for payment in invoice.payments],
    )


def invoice_summary(invoice: Invoice) -> InvoiceSummary:
    return InvoiceSummary(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        customer_id=invoice.customer_id,
        invoice_at=invoice.invoice_at,
        status=invoice.status.value,
        total_minor=invoice.total_minor,
        paid_minor=invoice.paid_minor,
        outstanding_minor=invoice.outstanding_minor,
    )


def payment_response(payment: Payment) -> PaymentResponse:
    return PaymentResponse(
        id=payment.id,
        invoice_id=payment.invoice_id,
        amount_minor=payment.amount_minor,
        method=payment.method,
        reference=payment.reference,
        paid_at=payment.paid_at,
        actor_id=payment.actor_id,
        created_at=payment.created_at,
    )


def get_invoice(db: DbSession, tenant_id: UUID, invoice_id: UUID) -> Invoice:
    invoice = db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
        .options(selectinload(Invoice.lines), selectinload(Invoice.payments))
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.post("/checkout/preview", response_model=CheckoutPreview)
def preview(data: CheckoutRequest, user: CurrentUser, db: DbSession):
    return preview_checkout(db, user, data)


@router.post("/checkout/confirm", response_model=InvoiceDetail, status_code=201)
def confirm(
    data: CheckoutRequest,
    user: CurrentUser,
    db: DbSession,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)],
):
    if user.role not in CHECKOUT_ROLES:
        raise HTTPException(status_code=403, detail="Checkout permission required")
    try:
        invoice = confirm_checkout(db, user, data, idempotency_key)
        db.commit()
        return invoice_detail(get_invoice(db, user.tenant_id, invoice.id))
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Checkout could not be completed; no invoice or stock changes were saved",
        ) from exc


@router.get("/invoices", response_model=InvoicePage)
def invoices(
    user: CurrentUser,
    db: DbSession,
    search: str = Query("", max_length=64),
    customer_id: UUID | None = None,
    payment_status: str = Query("all", pattern="^(all|unpaid|partially_paid|paid|outstanding)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conditions = [Invoice.tenant_id == user.tenant_id]
    if search.strip():
        conditions.append(Invoice.invoice_number.ilike(f"%{search.strip()}%"))
    if customer_id:
        conditions.append(Invoice.customer_id == customer_id)
    if payment_status == "unpaid":
        conditions.append(Invoice.status == InvoiceStatus.FINALIZED)
    elif payment_status == "partially_paid":
        conditions.append(Invoice.status == InvoiceStatus.PARTIALLY_PAID)
    elif payment_status == "paid":
        conditions.append(Invoice.status == InvoiceStatus.PAID)
    elif payment_status == "outstanding":
        conditions.extend(
            [
                Invoice.outstanding_minor > 0,
                Invoice.status.in_([InvoiceStatus.FINALIZED, InvoiceStatus.PARTIALLY_PAID]),
            ]
        )
    total = db.scalar(select(func.count()).select_from(Invoice).where(*conditions)) or 0
    total_outstanding = (
        db.scalar(
            select(func.coalesce(func.sum(Invoice.outstanding_minor), 0)).where(
                *conditions,
                Invoice.status.in_([InvoiceStatus.FINALIZED, InvoiceStatus.PARTIALLY_PAID]),
            )
        )
        or 0
    )
    records = db.scalars(
        select(Invoice)
        .where(*conditions)
        .order_by(Invoice.invoice_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return InvoicePage(
        items=[invoice_summary(item) for item in records],
        page=page,
        page_size=page_size,
        total=total,
        pages=max(1, (total + page_size - 1) // page_size),
        total_outstanding_minor=total_outstanding,
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetail)
def invoice(invoice_id: UUID, user: CurrentUser, db: DbSession):
    return invoice_detail(get_invoice(db, user.tenant_id, invoice_id))


@router.get("/invoices/{invoice_id}/payments", response_model=list[PaymentResponse])
def payments(invoice_id: UUID, user: CurrentUser, db: DbSession):
    get_invoice(db, user.tenant_id, invoice_id)
    records = db.scalars(
        select(Payment)
        .where(Payment.invoice_id == invoice_id, Payment.tenant_id == user.tenant_id)
        .order_by(Payment.paid_at.desc(), Payment.id.desc())
    ).all()
    return [payment_response(item) for item in records]


@router.post("/invoices/{invoice_id}/payments", response_model=PaymentResult, status_code=201)
def create_payment(
    invoice_id: UUID,
    data: PaymentCreate,
    user: CurrentUser,
    db: DbSession,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)],
):
    if user.role not in PAYMENT_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Payment recording permission required")
    try:
        payment = record_payment(db, user, invoice_id, data, idempotency_key)
        db.commit()
        invoice_record = get_invoice(db, user.tenant_id, invoice_id)
        return PaymentResult(
            payment=payment_response(payment), invoice=invoice_summary(invoice_record)
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Payment could not be recorded; no balance changes were saved",
        ) from exc
