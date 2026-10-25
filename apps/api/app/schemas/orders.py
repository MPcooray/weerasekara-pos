from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.order import OpticalOrderStatus, SupplierOrderStatus


class OrderCreate(BaseModel):
    customer_id: UUID
    visit_id: UUID | None = None
    examination_id: UUID
    invoice_id: UUID | None = None
    frame_product_id: UUID | None = None
    frame_details: str | None = Field(None, max_length=1000)
    lens_type: str = Field(min_length=1, max_length=100)
    lens_material: str | None = Field(None, max_length=100)
    refractive_index: str | None = Field(None, max_length=30)
    coatings: list[str] = Field(default_factory=list, max_length=20)
    tint: str | None = Field(None, max_length=100)
    right_lens_details: str | None = Field(None, max_length=2000)
    left_lens_details: str | None = Field(None, max_length=2000)
    fitting_instructions: str | None = Field(None, max_length=4000)
    expected_collection_date: date | None = None
    internal_notes: str | None = Field(None, max_length=4000)
    assigned_staff_id: UUID | None = None


class OrderUpdate(OrderCreate):
    expected_version: int = Field(ge=1)


class TransitionRequest(BaseModel):
    status: OpticalOrderStatus
    reason: str | None = Field(None, max_length=500)
    expected_version: int = Field(ge=1)


class SupplierTrackingInput(BaseModel):
    supplier_id: UUID
    supplier_reference: str | None = Field(None, max_length=120)
    ordered_on: date | None = None
    expected_delivery: date | None = None
    received_on: date | None = None
    status: SupplierOrderStatus
    notes: str | None = Field(None, max_length=2000)
    expected_version: int | None = Field(None, ge=1)


class QualityCheckInput(BaseModel):
    prescription_verified: bool
    lenses_inspected: bool
    frame_inspected: bool
    fitting_confirmed: bool
    remarks: str | None = Field(None, max_length=2000)


class CollectionInput(BaseModel):
    notes: str | None = Field(None, max_length=2000)
    allow_outstanding_balance: bool = False
    expected_version: int = Field(ge=1)


class EventResponse(BaseModel):
    id: UUID
    from_status: str | None
    to_status: str
    actor_id: UUID
    reason: str | None
    created_at: datetime


class SupplierTrackingResponse(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_reference: str | None
    ordered_on: date | None
    expected_delivery: date | None
    received_on: date | None
    status: str
    notes: str | None
    version: int


class QualityCheckResponse(BaseModel):
    id: UUID
    prescription_verified: bool
    lenses_inspected: bool
    frame_inspected: bool
    fitting_confirmed: bool
    remarks: str | None
    actor_id: UUID
    checked_at: datetime


class CollectionResponse(BaseModel):
    id: UUID
    actor_id: UUID
    collected_at: datetime
    notes: str | None
    outstanding_minor_at_collection: int | None
    outstanding_override: bool | None


class OrderResponse(BaseModel):
    id: UUID
    order_number: str
    customer_id: UUID
    visit_id: UUID | None
    examination_id: UUID
    invoice_id: UUID | None
    frame_product_id: UUID | None
    assigned_staff_id: UUID | None
    status: str
    expected_collection_date: date | None
    overdue: bool
    outstanding_minor: int | None
    frame_snapshot: dict | None
    prescription_snapshot: dict
    lens_type: str
    lens_material: str | None
    refractive_index: str | None
    coatings: list[str]
    tint: str | None
    right_lens_details: str | None
    left_lens_details: str | None
    fitting_instructions: str | None
    internal_notes: str | None
    created_at: datetime
    updated_at: datetime
    version: int
    events: list[EventResponse] = []
    supplier_order: SupplierTrackingResponse | None = None
    quality_check: QualityCheckResponse | None = None
    collection: CollectionResponse | None = None


class OrderPage(BaseModel):
    items: list[OrderResponse]
    page: int
    page_size: int
    total: int
    pages: int


class StaffOption(BaseModel):
    id: UUID
    full_name: str
    role: str
