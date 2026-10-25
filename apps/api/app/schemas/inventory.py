from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.inventory import MovementType
from app.models.product import ProductCategory
from app.schemas.customer import normalize_contact_phone


class SupplierBase(BaseModel):
    business_name: str = Field(min_length=2, max_length=160)
    contact_person: str | None = Field(default=None, max_length=160)
    telephone: str | None = None
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("telephone")
    @classmethod
    def phone(cls, value: str | None) -> str | None:
        return normalize_contact_phone(value) if value else None


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    business_name: str | None = Field(default=None, min_length=2, max_length=160)
    contact_person: str | None = Field(default=None, max_length=160)
    telephone: str | None = None
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)
    is_archived: bool | None = None

    @field_validator("telephone")
    @classmethod
    def phone(cls, value: str | None) -> str | None:
        return normalize_contact_phone(value) if value else None


class SupplierResponse(SupplierBase):
    id: UUID
    tenant_id: UUID
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ProductBase(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    sku: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._/-]+$")
    barcode: str | None = Field(default=None, min_length=4, max_length=64)
    category: ProductCategory
    brand: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=4000)
    supplier_id: UUID | None = None
    cost_price_minor: int = Field(ge=0, le=2_000_000_000)
    selling_price_minor: int = Field(ge=0, le=2_000_000_000)
    tax_rate: int = Field(default=0, ge=0, le=10000, description="Basis points")
    tax_inclusive: bool = True
    tax_exempt: bool = False
    track_stock: bool = True
    reorder_threshold: int = Field(default=0, ge=0)
    frame_material: str | None = None
    frame_color: str | None = None
    frame_shape: str | None = None
    frame_size: str | None = None
    bridge_size: str | None = None
    temple_length: str | None = None
    frame_style: str | None = None
    lens_type: str | None = None
    lens_material: str | None = None
    refractive_index: str | None = None
    coating_type: str | None = None
    tint: str | None = None
    made_to_order: bool = False
    contact_power: Decimal | None = None
    base_curve: Decimal | None = None
    diameter: Decimal | None = None
    pack_size: int | None = Field(default=None, ge=1)
    expiry_date: date | None = None

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def service_stock_policy(self):
        if self.category == ProductCategory.OPTICAL_SERVICE and self.track_stock:
            raise ValueError("Optical services cannot track stock")
        return self


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    sku: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._/-]+$"
    )
    barcode: str | None = Field(default=None, min_length=4, max_length=64)
    category: ProductCategory | None = None
    brand: str | None = None
    model: str | None = None
    description: str | None = None
    supplier_id: UUID | None = None
    cost_price_minor: int | None = Field(default=None, ge=0)
    selling_price_minor: int | None = Field(default=None, ge=0)
    tax_rate: int | None = Field(default=None, ge=0, le=10000)
    tax_inclusive: bool | None = None
    tax_exempt: bool | None = None
    track_stock: bool | None = None
    reorder_threshold: int | None = Field(default=None, ge=0)
    is_archived: bool | None = None
    frame_material: str | None = None
    frame_color: str | None = None
    frame_shape: str | None = None
    frame_size: str | None = None
    bridge_size: str | None = None
    temple_length: str | None = None
    frame_style: str | None = None
    lens_type: str | None = None
    lens_material: str | None = None
    refractive_index: str | None = None
    coating_type: str | None = None
    tint: str | None = None
    made_to_order: bool | None = None
    contact_power: Decimal | None = None
    base_curve: Decimal | None = None
    diameter: Decimal | None = None
    pack_size: int | None = Field(default=None, ge=1)
    expiry_date: date | None = None

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value


class ProductResponse(ProductBase):
    cost_price_minor: int | None = None
    supplier_id: UUID | None = None
    id: UUID
    tenant_id: UUID
    is_archived: bool
    quantity: int = 0
    created_at: datetime
    updated_at: datetime
    version: int
    stock_version: int = 1
    model_config = {"from_attributes": True}


class ProductPage(BaseModel):
    items: list[ProductResponse]
    page: int
    page_size: int
    total: int
    pages: int


class StockMutation(BaseModel):
    location_id: UUID | None = None
    quantity_delta: int = Field(ge=-1_000_000, le=1_000_000)
    movement_type: MovementType
    reason: str | None = Field(default=None, max_length=500)
    reference: str | None = Field(default=None, max_length=120)
    expected_version: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_direction(self):
        if self.quantity_delta == 0:
            raise ValueError("Quantity change cannot be zero")
        positive = {
            MovementType.OPENING_STOCK,
            MovementType.STOCK_RECEIVED,
            MovementType.CUSTOMER_RETURN,
        }
        negative = {MovementType.DAMAGED_STOCK, MovementType.SUPPLIER_RETURN}
        if self.movement_type in positive and self.quantity_delta < 0:
            raise ValueError("This movement type requires a positive quantity")
        if self.movement_type in negative and self.quantity_delta > 0:
            raise ValueError("This movement type requires a negative quantity")
        if self.movement_type in {MovementType.SALE_DEDUCTION, MovementType.SALE_REVERSAL}:
            raise ValueError(
                "Sale stock movements are reserved for the Phase 4 transaction service"
            )
        return self


class MovementResponse(BaseModel):
    id: UUID
    product_id: UUID
    location_id: UUID
    quantity_delta: int
    movement_type: MovementType
    reason: str | None
    reference: str | None
    actor_id: UUID
    balance_after: int
    created_at: datetime
    model_config = {"from_attributes": True}


class LocationResponse(BaseModel):
    id: UUID
    name: str
    code: str
    is_default: bool
    is_active: bool
    model_config = {"from_attributes": True}


class InventorySummary(BaseModel):
    active_products: int
    tracked_products: int
    total_units: int
    low_stock_products: int
    out_of_stock_products: int
    valuation_minor: int | None
    by_category: dict[str, int]
