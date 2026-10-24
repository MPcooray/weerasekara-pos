from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentUser, DbSession
from app.api.routes.reporting import branding_response
from app.models.customer import Customer
from app.models.finance import CreditNote, Invoice, Payment, Quotation, Refund
from app.models.tenant import Tenant
from app.schemas.reporting import PrintDocument, PrintLine

router = APIRouter(prefix="/print-documents", tags=["printing"])


def customer_name(db: DbSession, tenant_id: UUID, customer_id: UUID | None) -> str | None:
    if not customer_id:
        return None
    return db.scalar(
        select(Customer.full_name).where(
            Customer.id == customer_id, Customer.tenant_id == tenant_id
        )
    )


def brand(db: DbSession, tenant_id: UUID):
    return branding_response(db.get(Tenant, tenant_id))


@router.get("/{document_type}/{document_id}", response_model=PrintDocument)
def print_document(document_type: str, document_id: UUID, user: CurrentUser, db: DbSession):
    if document_type in {"invoice", "receipt"}:
        item = db.scalar(
            select(Invoice)
            .where(Invoice.id == document_id, Invoice.tenant_id == user.tenant_id)
            .options(selectinload(Invoice.lines))
        )
        if not item:
            raise HTTPException(404, "Invoice not found")
        return PrintDocument(
            document_type=document_type,
            document_id=item.id,
            document_number=item.invoice_number,
            occurred_at=item.invoice_at,
            status=item.status.value,
            customer_name=customer_name(db, user.tenant_id, item.customer_id),
            subtotal_minor=item.subtotal_minor,
            discount_minor=item.discount_minor,
            tax_minor=item.tax_minor,
            total_minor=item.total_minor,
            paid_minor=item.paid_minor,
            outstanding_minor=item.outstanding_minor,
            lines=[
                PrintLine(
                    description=line.product_name,
                    sku=line.sku,
                    quantity=line.quantity,
                    unit_price_minor=line.unit_price_minor,
                    discount_minor=line.line_discount_minor + line.invoice_discount_minor,
                    tax_minor=line.tax_minor,
                    total_minor=line.line_total_minor,
                )
                for line in item.lines
            ],
            branding=brand(db, user.tenant_id),
        )
    if document_type == "quotation":
        item = db.scalar(
            select(Quotation)
            .where(Quotation.id == document_id, Quotation.tenant_id == user.tenant_id)
            .options(selectinload(Quotation.lines))
        )
        if not item:
            raise HTTPException(404, "Quotation not found")
        return PrintDocument(
            document_type="quotation",
            document_id=item.id,
            document_number=item.quotation_number,
            occurred_at=item.issued_at or item.created_at,
            status=item.status.value,
            customer_name=customer_name(db, user.tenant_id, item.customer_id),
            subtotal_minor=item.subtotal_minor,
            discount_minor=item.discount_minor,
            tax_minor=item.tax_minor,
            total_minor=item.total_minor,
            lines=[
                PrintLine(
                    description=line.product_name,
                    sku=line.sku,
                    quantity=line.quantity,
                    unit_price_minor=line.unit_price_minor,
                    discount_minor=line.line_discount_minor + line.invoice_discount_minor,
                    tax_minor=line.tax_minor,
                    total_minor=line.line_total_minor,
                )
                for line in item.lines
            ],
            branding=brand(db, user.tenant_id),
        )
    if document_type == "credit-note":
        item = db.scalar(
            select(CreditNote)
            .where(CreditNote.id == document_id, CreditNote.tenant_id == user.tenant_id)
            .options(selectinload(CreditNote.lines))
        )
        if not item:
            raise HTTPException(404, "Credit note not found")
        invoice = db.scalar(
            select(Invoice).where(
                Invoice.id == item.invoice_id, Invoice.tenant_id == user.tenant_id
            )
        )
        return PrintDocument(
            document_type="credit-note",
            document_id=item.id,
            document_number=item.credit_note_number,
            occurred_at=item.issued_at or item.created_at,
            status=item.status.value,
            customer_name=customer_name(db, user.tenant_id, invoice.customer_id),
            related_number=invoice.invoice_number,
            reason=item.reason,
            subtotal_minor=sum(line.subtotal_minor for line in item.lines),
            discount_minor=sum(line.discount_minor for line in item.lines),
            tax_minor=sum(line.tax_minor for line in item.lines),
            total_minor=item.total_minor,
            lines=[
                PrintLine(
                    description=line.description,
                    quantity=line.quantity,
                    unit_price_minor=line.subtotal_minor // line.quantity,
                    discount_minor=line.discount_minor,
                    tax_minor=line.tax_minor,
                    total_minor=line.amount_minor,
                )
                for line in item.lines
            ],
            branding=brand(db, user.tenant_id),
        )
    if document_type == "payment":
        item = db.scalar(
            select(Payment).where(Payment.id == document_id, Payment.tenant_id == user.tenant_id)
        )
        if not item:
            raise HTTPException(404, "Payment not found")
        invoice = db.scalar(
            select(Invoice).where(
                Invoice.id == item.invoice_id, Invoice.tenant_id == user.tenant_id
            )
        )
        return PrintDocument(
            document_type="payment",
            document_id=item.id,
            document_number=f"PAY-{str(item.id).split('-')[0].upper()}",
            occurred_at=item.paid_at,
            status="recorded",
            customer_name=customer_name(db, user.tenant_id, invoice.customer_id),
            related_number=invoice.invoice_number,
            payment_method=item.method.value,
            external_reference=item.reference,
            subtotal_minor=item.amount_minor,
            discount_minor=0,
            tax_minor=0,
            total_minor=item.amount_minor,
            paid_minor=item.amount_minor,
            lines=[
                PrintLine(
                    description="Payment received",
                    quantity=1,
                    unit_price_minor=item.amount_minor,
                    discount_minor=0,
                    tax_minor=0,
                    total_minor=item.amount_minor,
                )
            ],
            branding=brand(db, user.tenant_id),
        )
    if document_type == "refund":
        item = db.scalar(
            select(Refund).where(Refund.id == document_id, Refund.tenant_id == user.tenant_id)
        )
        if not item:
            raise HTTPException(404, "Refund not found")
        invoice = db.scalar(
            select(Invoice).where(
                Invoice.id == item.invoice_id, Invoice.tenant_id == user.tenant_id
            )
        )
        return PrintDocument(
            document_type="refund",
            document_id=item.id,
            document_number=f"REF-{str(item.id).split('-')[0].upper()}",
            occurred_at=item.refunded_at,
            status=item.status.value,
            customer_name=customer_name(db, user.tenant_id, invoice.customer_id),
            related_number=invoice.invoice_number,
            payment_method=item.method.value,
            external_reference=item.reference,
            reason=item.reason,
            subtotal_minor=item.amount_minor,
            discount_minor=0,
            tax_minor=0,
            total_minor=item.amount_minor,
            lines=[
                PrintLine(
                    description="Refund issued",
                    quantity=1,
                    unit_price_minor=item.amount_minor,
                    discount_minor=0,
                    tax_minor=0,
                    total_minor=item.amount_minor,
                )
            ],
            branding=brand(db, user.tenant_id),
        )
    raise HTTPException(404, "Unsupported print document type")
