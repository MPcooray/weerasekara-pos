import enum
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    inspect,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import IdMixin, TimestampMixin


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    FINALIZED = "finalized"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"


class QuotationStatus(str, enum.Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    CONVERTED = "converted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"


class ReturnStatus(str, enum.Enum):
    DRAFT = "draft"
    FINALIZED = "finalized"
    CANCELLED = "cancelled"


class CreditNoteStatus(str, enum.Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    VOIDED = "voided"


class IdempotencyStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class InvoiceNumberSequence(Base):
    __tablename__ = "invoice_number_sequences"
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    next_number: Mapped[int] = mapped_column(Integer, default=1)


class Invoice(IdMixin, TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "invoice_number", name="uq_invoices_tenant_number"),
        CheckConstraint(
            "subtotal_minor >= 0 AND discount_minor >= 0 AND tax_minor >= 0",
            name="ck_invoice_amounts_nonnegative",
        ),
        CheckConstraint(
            "total_minor >= 0 AND paid_minor >= 0 AND outstanding_minor >= 0",
            name="ck_invoice_balances_nonnegative",
        ),
        CheckConstraint(
            "paid_minor + outstanding_minor = total_minor", name="ck_invoice_balance_equation"
        ),
    )
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    location_id: Mapped[UUID] = mapped_column(ForeignKey("inventory_locations.id"), index=True)
    invoice_number: Mapped[str] = mapped_column(String(32), index=True)
    customer_id: Mapped[UUID | None] = mapped_column(ForeignKey("customers.id"), index=True)
    examination_id: Mapped[UUID | None] = mapped_column(ForeignKey("examinations.id"))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), index=True)
    invoice_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    subtotal_minor: Mapped[int] = mapped_column(Integer)
    discount_minor: Mapped[int] = mapped_column(Integer)
    tax_minor: Mapped[int] = mapped_column(Integer)
    total_minor: Mapped[int] = mapped_column(Integer)
    paid_minor: Mapped[int] = mapped_column(Integer, default=0)
    outstanding_minor: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="invoice", order_by="Payment.paid_at"
    )


class InvoiceLine(IdMixin, Base):
    __tablename__ = "invoice_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_invoice_line_quantity"),
        CheckConstraint(
            "unit_price_minor >= 0 AND line_total_minor >= 0", name="ck_invoice_line_money"
        ),
    )
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id"), index=True)
    product_id: Mapped[UUID | None] = mapped_column(ForeignKey("products.id"))
    product_name: Mapped[str] = mapped_column(String(180))
    sku: Mapped[str | None] = mapped_column(String(64))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_minor: Mapped[int] = mapped_column(Integer)
    line_discount_minor: Mapped[int] = mapped_column(Integer, default=0)
    invoice_discount_minor: Mapped[int] = mapped_column(Integer, default=0)
    tax_rate_bps: Mapped[int] = mapped_column(Integer, default=0)
    tax_exempt: Mapped[bool] = mapped_column(default=False)
    tax_inclusive: Mapped[bool] = mapped_column(default=True)
    tax_minor: Mapped[int] = mapped_column(Integer, default=0)
    line_total_minor: Mapped[int] = mapped_column(Integer)
    invoice: Mapped[Invoice] = relationship(back_populates="lines")


class Payment(IdMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount_minor > 0", name="ck_payment_positive"),)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id"), index=True)
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod))
    amount_minor: Mapped[int] = mapped_column(Integer)
    reference: Mapped[str | None] = mapped_column(String(120))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    reversed_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("payments.id"))
    invoice: Mapped[Invoice] = relationship(back_populates="payments", foreign_keys=[invoice_id])


class Quotation(IdMixin, TimestampMixin, Base):
    __tablename__ = "quotations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "quotation_number", name="uq_quotations_tenant_number"),
    )
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    quotation_number: Mapped[str] = mapped_column(String(32))
    customer_id: Mapped[UUID | None] = mapped_column(ForeignKey("customers.id"))
    examination_id: Mapped[UUID | None] = mapped_column(ForeignKey("examinations.id"))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[QuotationStatus] = mapped_column(Enum(QuotationStatus))
    expires_on: Mapped[date | None] = mapped_column(Date)
    subtotal_minor: Mapped[int] = mapped_column(Integer)
    discount_minor: Mapped[int] = mapped_column(Integer)
    tax_minor: Mapped[int] = mapped_column(Integer)
    total_minor: Mapped[int] = mapped_column(Integer)
    converted_invoice_id: Mapped[UUID | None] = mapped_column(ForeignKey("invoices.id"))
    lines: Mapped[list["QuotationLine"]] = relationship(
        back_populates="quotation", cascade="all, delete-orphan"
    )


class QuotationLine(IdMixin, Base):
    __tablename__ = "quotation_lines"
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    quotation_id: Mapped[UUID] = mapped_column(ForeignKey("quotations.id"), index=True)
    product_id: Mapped[UUID | None] = mapped_column(ForeignKey("products.id"))
    product_name: Mapped[str] = mapped_column(String(180))
    sku: Mapped[str | None] = mapped_column(String(64))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_minor: Mapped[int] = mapped_column(Integer)
    line_discount_minor: Mapped[int] = mapped_column(Integer, default=0)
    invoice_discount_minor: Mapped[int] = mapped_column(Integer, default=0)
    tax_rate_bps: Mapped[int] = mapped_column(Integer, default=0)
    tax_exempt: Mapped[bool] = mapped_column(default=False)
    tax_inclusive: Mapped[bool] = mapped_column(default=True)
    tax_minor: Mapped[int] = mapped_column(Integer, default=0)
    line_total_minor: Mapped[int] = mapped_column(Integer)
    quotation: Mapped[Quotation] = relationship(back_populates="lines")


class Return(IdMixin, TimestampMixin, Base):
    __tablename__ = "returns"
    __table_args__ = (
        UniqueConstraint("tenant_id", "return_number", name="uq_returns_tenant_number"),
    )
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id"), index=True)
    return_number: Mapped[str] = mapped_column(String(32))
    status: Mapped[ReturnStatus] = mapped_column(Enum(ReturnStatus))
    reason: Mapped[str] = mapped_column(String(500))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    total_minor: Mapped[int] = mapped_column(Integer)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lines: Mapped[list["ReturnLine"]] = relationship(
        back_populates="return_record", cascade="all, delete-orphan"
    )


class ReturnLine(IdMixin, Base):
    __tablename__ = "return_lines"
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    return_id: Mapped[UUID] = mapped_column(ForeignKey("returns.id"))
    invoice_line_id: Mapped[UUID] = mapped_column(ForeignKey("invoice_lines.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    amount_minor: Mapped[int] = mapped_column(Integer)
    restock: Mapped[bool] = mapped_column(default=False)
    return_record: Mapped[Return] = relationship(back_populates="lines")


class CreditNote(IdMixin, TimestampMixin, Base):
    __tablename__ = "credit_notes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "credit_note_number", name="uq_credit_notes_tenant_number"),
    )
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id"))
    return_id: Mapped[UUID | None] = mapped_column(ForeignKey("returns.id"))
    credit_note_number: Mapped[str] = mapped_column(String(32))
    status: Mapped[CreditNoteStatus] = mapped_column(Enum(CreditNoteStatus))
    reason: Mapped[str] = mapped_column(String(500))
    total_minor: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lines: Mapped[list["CreditNoteLine"]] = relationship(
        back_populates="credit_note", cascade="all, delete-orphan"
    )


class CreditNoteLine(IdMixin, Base):
    __tablename__ = "credit_note_lines"
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    credit_note_id: Mapped[UUID] = mapped_column(ForeignKey("credit_notes.id"))
    invoice_line_id: Mapped[UUID | None] = mapped_column(ForeignKey("invoice_lines.id"))
    description: Mapped[str] = mapped_column(String(180))
    amount_minor: Mapped[int] = mapped_column(Integer)
    credit_note: Mapped[CreditNote] = relationship(back_populates="lines")


class FinancialIdempotency(IdMixin, Base):
    __tablename__ = "financial_idempotency"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "operation", "idempotency_key", name="uq_financial_idempotency"
        ),
    )
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    operation: Mapped[str] = mapped_column(String(50))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[IdempotencyStatus] = mapped_column(Enum(IdempotencyStatus))
    resource_type: Mapped[str | None] = mapped_column(String(50))
    resource_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


IMMUTABLE_INVOICE_FIELDS = {
    "tenant_id",
    "location_id",
    "invoice_number",
    "customer_id",
    "examination_id",
    "actor_id",
    "invoice_at",
    "subtotal_minor",
    "discount_minor",
    "tax_minor",
    "total_minor",
    "finalized_at",
}


@event.listens_for(Session, "before_flush")
def protect_finalized_financial_snapshots(session: Session, *_args: object) -> None:
    for obj in session.dirty:
        if isinstance(obj, Invoice):
            state = inspect(obj)
            old_status = state.attrs.status.history.deleted
            finalized_before = old_status and old_status[0] != InvoiceStatus.DRAFT
            finalized_now = not old_status and obj.status != InvoiceStatus.DRAFT
            if (finalized_before or finalized_now) and any(
                state.attrs[name].history.has_changes() for name in IMMUTABLE_INVOICE_FIELDS
            ):
                raise ValueError("Finalized invoice snapshots are immutable")
        elif isinstance(obj, InvoiceLine) and obj.invoice.status != InvoiceStatus.DRAFT:
            raise ValueError("Finalized invoice line snapshots are immutable")
        elif isinstance(obj, Payment):
            changed = {attr.key for attr in inspect(obj).attrs if attr.history.has_changes()}
            if changed - {"reversed_by_id"}:
                raise ValueError("Recorded payments are immutable")
        elif isinstance(obj, Quotation):
            old = inspect(obj).attrs.status.history.deleted
            if (not old and obj.status != QuotationStatus.DRAFT) or (
                old and old[0] != QuotationStatus.DRAFT
            ):
                raise ValueError("Issued quotation snapshots are immutable")
        elif isinstance(obj, QuotationLine) and obj.quotation.status != QuotationStatus.DRAFT:
            raise ValueError("Issued quotation line snapshots are immutable")
        elif isinstance(obj, Return):
            old = inspect(obj).attrs.status.history.deleted
            if (not old and obj.status != ReturnStatus.DRAFT) or (
                old and old[0] != ReturnStatus.DRAFT
            ):
                raise ValueError("Finalized return snapshots are immutable")
        elif isinstance(obj, ReturnLine) and obj.return_record.status != ReturnStatus.DRAFT:
            raise ValueError("Finalized return line snapshots are immutable")
        elif isinstance(obj, CreditNote):
            old = inspect(obj).attrs.status.history.deleted
            if (not old and obj.status != CreditNoteStatus.DRAFT) or (
                old and old[0] != CreditNoteStatus.DRAFT
            ):
                raise ValueError("Issued credit note snapshots are immutable")
        elif isinstance(obj, CreditNoteLine) and obj.credit_note.status != CreditNoteStatus.DRAFT:
            raise ValueError("Issued credit note line snapshots are immutable")
    for obj in session.deleted:
        if isinstance(obj, Invoice) and obj.status != InvoiceStatus.DRAFT:
            raise ValueError("Finalized invoices cannot be deleted")
        if isinstance(obj, InvoiceLine) and obj.invoice.status != InvoiceStatus.DRAFT:
            raise ValueError("Finalized invoice line snapshots cannot be deleted")
        if isinstance(obj, (Payment, Quotation, Return, CreditNote)):
            status = getattr(obj, "status", None)
            if status is None or status.value not in {"draft"}:
                raise ValueError("Finalized financial records cannot be deleted")
