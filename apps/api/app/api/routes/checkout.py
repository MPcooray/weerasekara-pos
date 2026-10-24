from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentUser, DbSession
from app.models.finance import Invoice
from app.models.user import CHECKOUT_ROLES
from app.schemas.checkout import (
    CheckoutLineResult,
    CheckoutPreview,
    CheckoutRequest,
    InvoiceDetail,
    InvoiceSummary,
)
from app.services.checkout import confirm_checkout, preview_checkout

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
    )


def get_invoice(db: DbSession, tenant_id: UUID, invoice_id: UUID) -> Invoice:
    invoice = db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
        .options(selectinload(Invoice.lines))
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


@router.get("/invoices", response_model=list[InvoiceSummary])
def invoices(user: CurrentUser, db: DbSession):
    records = db.scalars(
        select(Invoice)
        .where(Invoice.tenant_id == user.tenant_id)
        .order_by(Invoice.invoice_at.desc())
        .limit(200)
    ).all()
    return [
        InvoiceSummary(
            id=x.id,
            invoice_number=x.invoice_number,
            customer_id=x.customer_id,
            invoice_at=x.invoice_at,
            status=x.status.value,
            total_minor=x.total_minor,
            paid_minor=x.paid_minor,
            outstanding_minor=x.outstanding_minor,
        )
        for x in records
    ]


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetail)
def invoice(invoice_id: UUID, user: CurrentUser, db: DbSession):
    return invoice_detail(get_invoice(db, user.tenant_id, invoice_id))
