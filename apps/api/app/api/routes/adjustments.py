from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentUser, DbSession
from app.api.routes.checkout import get_invoice, invoice_detail
from app.core.time import colombo_today
from app.models.finance import CreditNote, Quotation, Refund, Return
from app.models.user import (
    QUOTATION_WRITE_ROLES,
    REFUND_WRITE_ROLES,
    RETURN_APPROVE_ROLES,
    RETURN_REQUEST_ROLES,
)
from app.schemas.adjustments import (
    ConversionPreview,
    ConversionRequest,
    CreditLineResponse,
    CreditNoteResponse,
    QuotationCreate,
    QuotationLineResponse,
    QuotationPage,
    QuotationResponse,
    RefundCreate,
    RefundResponse,
    ReturnCreate,
    ReturnLineResponse,
    ReturnResponse,
)
from app.schemas.checkout import InvoiceDetail
from app.services.adjustments import (
    approve_return,
    conversion_preview,
    convert_quotation,
    issue_quotation,
    record_refund,
    request_return,
    save_quotation,
)

router = APIRouter(tags=["financial-adjustments"])


def quotation_response(item: Quotation) -> QuotationResponse:
    status = item.status.value
    if status == "issued" and item.expires_on and item.expires_on < colombo_today():
        status = "expired"
    return QuotationResponse(
        id=item.id,
        quotation_number=item.quotation_number,
        customer_id=item.customer_id,
        examination_id=item.examination_id,
        status=status,
        expires_on=item.expires_on,
        subtotal_minor=item.subtotal_minor,
        discount_minor=item.discount_minor,
        tax_minor=item.tax_minor,
        total_minor=item.total_minor,
        converted_invoice_id=item.converted_invoice_id,
        issued_at=item.issued_at,
        notes=item.notes,
        created_at=item.created_at,
        updated_at=item.updated_at,
        lines=[
            QuotationLineResponse(
                id=x.id,
                product_id=x.product_id,
                product_name=x.product_name,
                sku=x.sku,
                quantity=x.quantity,
                unit_price_minor=x.unit_price_minor,
                line_discount_minor=x.line_discount_minor,
                invoice_discount_minor=x.invoice_discount_minor,
                tax_minor=x.tax_minor,
                line_total_minor=x.line_total_minor,
            )
            for x in item.lines
        ],
    )


def get_quotation(db: DbSession, tenant_id: UUID, quotation_id: UUID) -> Quotation:
    item = db.scalar(
        select(Quotation)
        .where(Quotation.id == quotation_id, Quotation.tenant_id == tenant_id)
        .options(selectinload(Quotation.lines))
    )
    if not item:
        raise HTTPException(404, "Quotation not found")
    return item


@router.post("/quotations", response_model=QuotationResponse, status_code=201)
def create_quotation(data: QuotationCreate, user: CurrentUser, db: DbSession):
    if user.role not in QUOTATION_WRITE_ROLES:
        raise HTTPException(403, "Quotation permission required")
    try:
        item = save_quotation(db, user, data)
        db.commit()
        return quotation_response(get_quotation(db, user.tenant_id, item.id))
    except HTTPException:
        db.rollback()
        raise


@router.put("/quotations/{quotation_id}", response_model=QuotationResponse)
def update_quotation(quotation_id: UUID, data: QuotationCreate, user: CurrentUser, db: DbSession):
    if user.role not in QUOTATION_WRITE_ROLES:
        raise HTTPException(403, "Quotation permission required")
    try:
        item = save_quotation(db, user, data, get_quotation(db, user.tenant_id, quotation_id))
        db.commit()
        return quotation_response(get_quotation(db, user.tenant_id, item.id))
    except HTTPException:
        db.rollback()
        raise


@router.get("/quotations", response_model=QuotationPage)
def quotations(
    user: CurrentUser,
    db: DbSession,
    search: str = Query("", max_length=64),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conditions = [Quotation.tenant_id == user.tenant_id]
    if search.strip():
        conditions.append(Quotation.quotation_number.ilike(f"%{search.strip()}%"))
    total = db.scalar(select(func.count()).select_from(Quotation).where(*conditions)) or 0
    items = db.scalars(
        select(Quotation)
        .where(*conditions)
        .options(selectinload(Quotation.lines))
        .order_by(Quotation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return QuotationPage(
        items=[quotation_response(x) for x in items],
        page=page,
        page_size=page_size,
        total=total,
        pages=max(1, (total + page_size - 1) // page_size),
    )


@router.get("/quotations/{quotation_id}", response_model=QuotationResponse)
def quotation(quotation_id: UUID, user: CurrentUser, db: DbSession):
    return quotation_response(get_quotation(db, user.tenant_id, quotation_id))


@router.post("/quotations/{quotation_id}/issue", response_model=QuotationResponse)
def issue(
    quotation_id: UUID,
    user: CurrentUser,
    db: DbSession,
    key: Annotated[str, Header(alias="Idempotency-Key", min_length=8)],
):
    if user.role not in QUOTATION_WRITE_ROLES:
        raise HTTPException(403, "Quotation permission required")
    try:
        item = issue_quotation(db, user, quotation_id, key)
        db.commit()
        return quotation_response(get_quotation(db, user.tenant_id, item.id))
    except HTTPException:
        db.rollback()
        raise


@router.get("/quotations/{quotation_id}/conversion-preview", response_model=ConversionPreview)
def preview_conversion(quotation_id: UUID, user: CurrentUser, db: DbSession):
    item = get_quotation(db, user.tenant_id, quotation_id)
    _, current, differences = conversion_preview(db, user, item)
    return ConversionPreview(
        changed=bool(differences),
        differences=differences,
        current_total_minor=current,
        quoted_total_minor=item.total_minor,
    )


@router.post("/quotations/{quotation_id}/convert", response_model=InvoiceDetail, status_code=201)
def convert(
    quotation_id: UUID,
    data: ConversionRequest,
    user: CurrentUser,
    db: DbSession,
    key: Annotated[str, Header(alias="Idempotency-Key", min_length=8)],
):
    if user.role not in QUOTATION_WRITE_ROLES:
        raise HTTPException(403, "Quotation permission required")
    try:
        invoice = convert_quotation(db, user, quotation_id, data.approve_changes, key)
        db.commit()
        return invoice_detail(get_invoice(db, user.tenant_id, invoice.id))
    except HTTPException:
        db.rollback()
        raise


def return_response(item: Return, credit_id: UUID | None = None) -> ReturnResponse:
    return ReturnResponse(
        id=item.id,
        invoice_id=item.invoice_id,
        return_number=item.return_number,
        status=item.status.value,
        reason=item.reason,
        total_minor=item.total_minor,
        finalized_at=item.finalized_at,
        created_at=item.created_at,
        lines=[
            ReturnLineResponse(
                id=x.id,
                invoice_line_id=x.invoice_line_id,
                quantity=x.quantity,
                amount_minor=x.amount_minor,
                restock=x.restock,
            )
            for x in item.lines
        ],
        credit_note_id=credit_id,
    )


def credit_response(item: CreditNote) -> CreditNoteResponse:
    return CreditNoteResponse(
        id=item.id,
        invoice_id=item.invoice_id,
        return_id=item.return_id,
        credit_note_number=item.credit_note_number,
        status=item.status.value,
        reason=item.reason,
        total_minor=item.total_minor,
        issued_at=item.issued_at,
        lines=[
            CreditLineResponse(
                description=x.description,
                quantity=x.quantity,
                subtotal_minor=x.subtotal_minor,
                discount_minor=x.discount_minor,
                tax_minor=x.tax_minor,
                amount_minor=x.amount_minor,
            )
            for x in item.lines
        ],
    )


@router.post("/invoices/{invoice_id}/returns", response_model=ReturnResponse, status_code=201)
def create_return(
    invoice_id: UUID,
    data: ReturnCreate,
    user: CurrentUser,
    db: DbSession,
    key: Annotated[str, Header(alias="Idempotency-Key", min_length=8)],
):
    if user.role not in RETURN_REQUEST_ROLES:
        raise HTTPException(403, "Return request permission required")
    try:
        item = request_return(db, user, invoice_id, data, key)
        db.commit()
        item = db.scalar(
            select(Return).where(Return.id == item.id).options(selectinload(Return.lines))
        )
        return return_response(item)
    except HTTPException:
        db.rollback()
        raise


@router.get("/invoices/{invoice_id}/returns", response_model=list[ReturnResponse])
def invoice_returns(invoice_id: UUID, user: CurrentUser, db: DbSession):
    get_invoice(db, user.tenant_id, invoice_id)
    items = db.scalars(
        select(Return)
        .where(Return.invoice_id == invoice_id, Return.tenant_id == user.tenant_id)
        .options(selectinload(Return.lines))
        .order_by(Return.created_at.desc())
    ).all()
    return [
        return_response(x, db.scalar(select(CreditNote.id).where(CreditNote.return_id == x.id)))
        for x in items
    ]


@router.post("/returns/{return_id}/approve", response_model=ReturnResponse)
def approve(
    return_id: UUID,
    user: CurrentUser,
    db: DbSession,
    key: Annotated[str, Header(alias="Idempotency-Key", min_length=8)],
):
    if user.role not in RETURN_APPROVE_ROLES:
        raise HTTPException(403, "Return approval permission required")
    try:
        item, credit = approve_return(db, user, return_id, key)
        db.commit()
        item = db.scalar(
            select(Return).where(Return.id == item.id).options(selectinload(Return.lines))
        )
        return return_response(item, credit.id)
    except HTTPException:
        db.rollback()
        raise


@router.get("/credit-notes/{credit_id}", response_model=CreditNoteResponse)
def credit_note(credit_id: UUID, user: CurrentUser, db: DbSession):
    item = db.scalar(
        select(CreditNote)
        .where(CreditNote.id == credit_id, CreditNote.tenant_id == user.tenant_id)
        .options(selectinload(CreditNote.lines))
    )
    if not item:
        raise HTTPException(404, "Credit note not found")
    return credit_response(item)


def refund_response(item: Refund) -> RefundResponse:
    return RefundResponse(
        id=item.id,
        invoice_id=item.invoice_id,
        credit_note_id=item.credit_note_id,
        amount_minor=item.amount_minor,
        method=item.method,
        reason=item.reason,
        reference=item.reference,
        actor_id=item.actor_id,
        refunded_at=item.refunded_at,
    )


@router.post("/credit-notes/{credit_id}/refunds", response_model=RefundResponse, status_code=201)
def refund(
    credit_id: UUID,
    data: RefundCreate,
    user: CurrentUser,
    db: DbSession,
    key: Annotated[str, Header(alias="Idempotency-Key", min_length=8)],
):
    if user.role not in REFUND_WRITE_ROLES:
        raise HTTPException(403, "Refund permission required")
    try:
        item = record_refund(db, user, credit_id, data, key)
        db.commit()
        db.refresh(item)
        return refund_response(item)
    except HTTPException:
        db.rollback()
        raise


@router.get("/credit-notes/{credit_id}/refunds", response_model=list[RefundResponse])
def refunds(credit_id: UUID, user: CurrentUser, db: DbSession):
    exists = db.scalar(
        select(CreditNote.id).where(
            CreditNote.id == credit_id, CreditNote.tenant_id == user.tenant_id
        )
    )
    if not exists:
        raise HTTPException(404, "Credit note not found")
    items = db.scalars(
        select(Refund)
        .where(Refund.credit_note_id == credit_id, Refund.tenant_id == user.tenant_id)
        .order_by(Refund.refunded_at.desc())
    ).all()
    return [refund_response(x) for x in items]
