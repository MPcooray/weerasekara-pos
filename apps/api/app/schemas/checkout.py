from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


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


class InvoiceDetail(InvoiceSummary):
    location_id: UUID
    examination_id: UUID | None
    actor_id: UUID
    subtotal_minor: int
    discount_minor: int
    tax_minor: int
    notes: str | None
    lines: list[CheckoutLineResult]
