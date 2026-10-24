from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.finance import PaymentMethod


class QuotationLineInput(BaseModel):
    product_id: UUID
    quantity: int = Field(ge=1, le=10_000)
    line_discount_minor: int = Field(default=0, ge=0)


class QuotationCreate(BaseModel):
    customer_id: UUID | None = None
    examination_id: UUID | None = None
    expires_on: date | None = None
    invoice_discount_minor: int = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=4000)
    lines: list[QuotationLineInput] = Field(min_length=1, max_length=200)


class QuotationLineResponse(BaseModel):
    id: UUID
    product_id: UUID | None
    product_name: str
    sku: str | None
    quantity: int
    unit_price_minor: int
    line_discount_minor: int
    invoice_discount_minor: int
    tax_minor: int
    line_total_minor: int


class QuotationResponse(BaseModel):
    id: UUID
    quotation_number: str
    customer_id: UUID | None
    examination_id: UUID | None
    status: str
    expires_on: date | None
    subtotal_minor: int
    discount_minor: int
    tax_minor: int
    total_minor: int
    converted_invoice_id: UUID | None
    issued_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    lines: list[QuotationLineResponse]


class QuotationPage(BaseModel):
    items: list[QuotationResponse]
    page: int
    page_size: int
    total: int
    pages: int


class ConversionRequest(BaseModel):
    approve_changes: bool = False


class ConversionPreview(BaseModel):
    changed: bool
    differences: list[str]
    current_total_minor: int
    quoted_total_minor: int


class ReturnLineInput(BaseModel):
    invoice_line_id: UUID
    quantity: int = Field(ge=1)
    restock: bool = False


class ReturnCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    lines: list[ReturnLineInput] = Field(min_length=1)


class ReturnLineResponse(BaseModel):
    id: UUID
    invoice_line_id: UUID
    quantity: int
    amount_minor: int
    restock: bool


class ReturnResponse(BaseModel):
    id: UUID
    invoice_id: UUID
    return_number: str
    status: str
    reason: str
    total_minor: int
    finalized_at: datetime | None
    created_at: datetime
    lines: list[ReturnLineResponse]
    credit_note_id: UUID | None = None


class CreditLineResponse(BaseModel):
    description: str
    quantity: int
    subtotal_minor: int
    discount_minor: int
    tax_minor: int
    amount_minor: int


class CreditNoteResponse(BaseModel):
    id: UUID
    invoice_id: UUID
    return_id: UUID | None
    credit_note_number: str
    status: str
    reason: str
    total_minor: int
    issued_at: datetime | None
    lines: list[CreditLineResponse]


class RefundCreate(BaseModel):
    amount_minor: int = Field(gt=0, le=2_000_000_000)
    method: PaymentMethod
    reason: str = Field(min_length=3, max_length=500)
    reference: str | None = Field(default=None, max_length=120)

    @field_validator("reference")
    @classmethod
    def clean_reference(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class RefundResponse(BaseModel):
    id: UUID
    invoice_id: UUID
    credit_note_id: UUID
    amount_minor: int
    method: PaymentMethod
    reason: str
    reference: str | None
    actor_id: UUID
    refunded_at: datetime
