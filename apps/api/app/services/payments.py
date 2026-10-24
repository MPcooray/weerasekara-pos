import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.finance import (
    FinancialIdempotency,
    IdempotencyStatus,
    Invoice,
    InvoiceStatus,
    Payment,
)
from app.models.user import User
from app.schemas.checkout import PaymentCreate
from app.services.audit import record_audit
from app.services.financial_calculations import calculate_balance


def payment_request_hash(invoice_id: UUID, data: PaymentCreate) -> str:
    canonical = json.dumps(
        {"invoice_id": str(invoice_id), **data.model_dump(mode="json")},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def record_payment(
    db: Session, user: User, invoice_id: UUID, data: PaymentCreate, idempotency_key: str
) -> Payment:
    digest = payment_request_hash(invoice_id, data)
    existing = db.scalar(
        select(FinancialIdempotency).where(
            FinancialIdempotency.tenant_id == user.tenant_id,
            FinancialIdempotency.operation == "payment",
            FinancialIdempotency.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(
                status_code=409, detail="Idempotency key was already used with a different payment"
            )
        if existing.status == IdempotencyStatus.COMPLETED and existing.resource_id:
            payment = db.scalar(
                select(Payment).where(
                    Payment.id == existing.resource_id, Payment.tenant_id == user.tenant_id
                )
            )
            if payment:
                return payment
        raise HTTPException(status_code=409, detail="Payment is already in progress")

    claim = FinancialIdempotency(
        tenant_id=user.tenant_id,
        operation="payment",
        idempotency_key=idempotency_key,
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
                FinancialIdempotency.operation == "payment",
                FinancialIdempotency.idempotency_key == idempotency_key,
            )
        )
        if existing and existing.request_hash != digest:
            raise HTTPException(
                status_code=409, detail="Idempotency key was already used with a different payment"
            ) from exc
        if existing and existing.status == IdempotencyStatus.COMPLETED and existing.resource_id:
            payment = db.get(Payment, existing.resource_id)
            if payment:
                return payment
        raise HTTPException(status_code=409, detail="Payment is already in progress") from exc

    invoice = db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
        .with_for_update()
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status not in {InvoiceStatus.FINALIZED, InvoiceStatus.PARTIALLY_PAID}:
        raise HTTPException(status_code=409, detail="Payments require an unpaid finalized invoice")

    new_paid = invoice.paid_minor + data.amount_minor
    try:
        outstanding = calculate_balance(invoice.total_minor, new_paid)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    now = datetime.now(UTC)
    payment = Payment(
        tenant_id=user.tenant_id,
        invoice_id=invoice.id,
        amount_minor=data.amount_minor,
        method=data.method,
        reference=data.reference,
        actor_id=user.id,
        paid_at=now,
        created_at=now,
    )
    db.add(payment)
    invoice.paid_minor = new_paid
    invoice.outstanding_minor = outstanding
    invoice.status = InvoiceStatus.PAID if outstanding == 0 else InvoiceStatus.PARTIALLY_PAID
    db.flush()
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="payment.recorded",
        entity_type="payment",
        entity_id=payment.id,
    )
    claim.status = IdempotencyStatus.COMPLETED
    claim.resource_type = "payment"
    claim.resource_id = payment.id
    claim.completed_at = now
    db.flush()
    return payment
