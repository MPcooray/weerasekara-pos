import re
from datetime import UTC, date, datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.customer import Gender
from app.models.visit import VisitStatus

PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
SRI_LANKAN_MOBILE_PATTERN = re.compile(r"^(?:\+94|0)7\d{8}$")
SRI_LANKAN_PHONE_PATTERN = re.compile(r"^(?:\+94|0)\d{9}$")


def normalize_phone(value: str) -> str:
    normalized = re.sub(r"[\s()-]", "", value)
    if normalized.startswith("0094"):
        normalized = "+94" + normalized[4:]
    if SRI_LANKAN_MOBILE_PATTERN.fullmatch(normalized):
        return "+94" + normalized[1:] if normalized.startswith("0") else normalized
    if PHONE_PATTERN.fullmatch(normalized):
        return normalized
    raise ValueError("Enter a valid Sri Lankan mobile number or international number")


def normalize_contact_phone(value: str) -> str:
    normalized = re.sub(r"[\s()-]", "", value)
    if normalized.startswith("0094"):
        normalized = "+94" + normalized[4:]
    if SRI_LANKAN_PHONE_PATTERN.fullmatch(normalized):
        return "+94" + normalized[1:] if normalized.startswith("0") else normalized
    if PHONE_PATTERN.fullmatch(normalized):
        return normalized
    raise ValueError("Enter a valid Sri Lankan or international phone number")


class CustomerBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    mobile_number: str
    alternative_contact_number: str | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None
    address: str | None = Field(default=None, max_length=500)
    email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("full_name", "address", "notes")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None

    @field_validator("mobile_number")
    @classmethod
    def validate_mobile(cls, value: str) -> str:
        return normalize_phone(value)

    @field_validator("alternative_contact_number")
    @classmethod
    def validate_alternative(cls, value: str | None) -> str | None:
        return normalize_contact_phone(value) if value else None

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date(cls, value: date | None) -> date | None:
        if value and value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    mobile_number: str | None = None
    alternative_contact_number: str | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None
    address: str | None = Field(default=None, max_length=500)
    email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("full_name", "address", "notes")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None

    @field_validator("mobile_number")
    @classmethod
    def validate_mobile(cls, value: str | None) -> str | None:
        return normalize_phone(value) if value else None

    @field_validator("alternative_contact_number")
    @classmethod
    def validate_alternative(cls, value: str | None) -> str | None:
        return normalize_contact_phone(value) if value else None

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date(cls, value: date | None) -> date | None:
        if value and value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value


class VisitCreate(BaseModel):
    visit_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    purpose: str = Field(min_length=2, max_length=200)
    assigned_staff_id: UUID | None = None
    status: VisitStatus = VisitStatus.OPEN
    notes: str | None = Field(default=None, max_length=4000)


class VisitUpdate(BaseModel):
    visit_at: datetime | None = None
    purpose: str | None = Field(default=None, min_length=2, max_length=200)
    assigned_staff_id: UUID | None = None
    status: VisitStatus | None = None
    notes: str | None = Field(default=None, max_length=4000)


class VisitResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    customer_id: UUID
    visit_at: datetime
    purpose: str
    assigned_staff_id: UUID | None
    status: VisitStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomerResponse(CustomerBase):
    id: UUID
    tenant_id: UUID
    customer_number: str
    created_by_id: UUID
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomerDetail(CustomerResponse):
    visits: list[VisitResponse] = []


class CustomerCreateResponse(BaseModel):
    customer: CustomerResponse
    duplicate_warnings: list[str] = []


class CustomerPage(BaseModel):
    items: list[CustomerResponse]
    page: int
    page_size: int
    total: int
    pages: int
