from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class BrandingUpdate(BaseModel):
    business_display_name: str | None = Field(None, max_length=160)
    business_address: str | None = Field(None, max_length=1000)
    business_contact: str | None = Field(None, max_length=240)
    logo_url: HttpUrl | None = None
    invoice_footer: str | None = Field(None, max_length=500)
    receipt_footer: str | None = Field(None, max_length=500)
    business_registration: str | None = Field(None, max_length=120)
    tax_registration: str | None = Field(None, max_length=120)


class BrandingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    business_display_name: str
    business_address: str | None
    business_contact: str | None
    logo_url: str | None
    invoice_footer: str | None
    receipt_footer: str | None
    business_registration: str | None
    tax_registration: str | None
    default_currency: str


class NamedAmount(BaseModel):
    name: str
    amount_minor: int
    quantity: int = 0


class TrendPoint(BaseModel):
    date: date
    invoiced_minor: int
    payments_minor: int


class FinancialReport(BaseModel):
    date_from: date
    date_to: date
    timezone: str = "Asia/Colombo"
    invoiced_sales_minor: int
    payments_received_minor: int
    refunds_minor: int
    outstanding_minor: int
    credit_notes_minor: int
    discounts_minor: int
    tax_minor: int
    payment_methods: list[NamedAmount]
    top_products: list[NamedAmount]
    sales_by_staff: list[NamedAmount]
    trend: list[TrendPoint]


class RecentTransaction(BaseModel):
    kind: str
    reference: str
    amount_minor: int
    occurred_at: datetime


class DashboardResponse(BaseModel):
    today_invoiced_minor: int
    today_payments_minor: int
    outstanding_minor: int
    today_refunds_minor: int
    pending_quotations: int
    low_stock_products: int
    recent_transactions: list[RecentTransaction]
    trend: list[TrendPoint]


class PrintLine(BaseModel):
    description: str
    sku: str | None = None
    quantity: int
    unit_price_minor: int
    discount_minor: int
    tax_minor: int
    total_minor: int


class PrintDocument(BaseModel):
    document_type: str
    document_id: UUID
    document_number: str
    occurred_at: datetime
    status: str
    customer_name: str | None = None
    related_number: str | None = None
    payment_method: str | None = None
    external_reference: str | None = None
    reason: str | None = None
    subtotal_minor: int
    discount_minor: int
    tax_minor: int
    total_minor: int
    paid_minor: int = 0
    outstanding_minor: int = 0
    lines: list[PrintLine]
    branding: BrandingResponse
