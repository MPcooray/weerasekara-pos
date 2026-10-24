from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.finance import PaymentMethod


class CheckoutLineInput(BaseModel):
    product_id: UUID
    quantity: int = Field(ge=1, le=10_000)
    line_discount_minor: int = Field(default=0, ge=0)
    expected_unit_price_minor: int | None = Field(default=None, ge=0)


class CheckoutRequest(BaseModel):
    location_id: UUID | None = None
    customer_id: UUID | None = None
    examination_id: UUID | None = None
    invoice_discount_minor: int = Field(default=0, ge=0)
    lines: list[CheckoutLineInput] = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)


class CheckoutLineResult(BaseModel):
    product_id: UUID
    product_name: str
    sku: str | None
    quantity: int
    unit_price_minor: int
    line_discount_minor: int
    invoice_discount_minor: int
    tax_rate_bps: int
    tax_exempt: bool
    tax_inclusive: bool
    tax_minor: int
    line_total_minor: int
    stock_available: int | None


class CheckoutPreview(BaseModel):
    lines: list[CheckoutLineResult]
    subtotal_minor: int
    discount_minor: int
    tax_minor: int
    total_minor: int
    paid_minor: int = 0
    outstanding_minor: int


class InvoiceSummary(BaseModel):
    id: UUID
    invoice_number: str
    customer_id: UUID | None
    invoice_at: datetime
    status: str
    total_minor: int
    paid_minor: int
    outstanding_minor: int


class InvoicePage(BaseModel):
    items: list[InvoiceSummary]
    page: int
    page_size: int
    total: int
    pages: int
    total_outstanding_minor: int


class PaymentCreate(BaseModel):
    amount_minor: int = Field(gt=0, le=2_000_000_000)
    method: PaymentMethod
    reference: str | None = Field(default=None, max_length=120)

    @field_validator("reference")
    @classmethod
    def clean_reference(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class PaymentResponse(BaseModel):
    id: UUID
    invoice_id: UUID
    amount_minor: int
    method: PaymentMethod
    reference: str | None
    paid_at: datetime
    actor_id: UUID
    created_at: datetime


class PaymentResult(BaseModel):
    payment: PaymentResponse
    invoice: InvoiceSummary


class InvoiceDetail(InvoiceSummary):
    location_id: UUID
    examination_id: UUID | None
    actor_id: UUID
    subtotal_minor: int
    discount_minor: int
    tax_minor: int
    notes: str | None
    lines: list[CheckoutLineResult]
    payments: list[PaymentResponse] = Field(default_factory=list)
