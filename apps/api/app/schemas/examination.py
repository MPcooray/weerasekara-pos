from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import get_settings
from app.models.examination import ExaminationStatus, PrescriptionType

POWER_FIELDS = {"od_sphere", "od_cylinder", "os_sphere", "os_cylinder"}
ADD_FIELDS = {"od_add", "os_add"}
PD_FIELDS = {"pd_binocular", "pd_right", "pd_left"}
MEASUREMENT_FIELDS = (
    POWER_FIELDS
    | ADD_FIELDS
    | PD_FIELDS
    | {"od_axis", "os_axis", "od_distance_va", "os_distance_va", "od_near_va", "os_near_va"}
)


class ExaminationFields(BaseModel):
    prescription_type: PrescriptionType | None = None
    expires_on: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    od_sphere: Decimal | None = None
    od_cylinder: Decimal | None = None
    od_axis: int | None = Field(default=None, ge=0, le=180)
    od_add: Decimal | None = None
    od_distance_va: str | None = Field(default=None, max_length=20)
    od_near_va: str | None = Field(default=None, max_length=20)
    od_prism: Decimal | None = Field(default=None, ge=0, le=20)
    od_prism_base: str | None = Field(default=None, max_length=30)
    od_notes: str | None = Field(default=None, max_length=2000)
    os_sphere: Decimal | None = None
    os_cylinder: Decimal | None = None
    os_axis: int | None = Field(default=None, ge=0, le=180)
    os_add: Decimal | None = None
    os_distance_va: str | None = Field(default=None, max_length=20)
    os_near_va: str | None = Field(default=None, max_length=20)
    os_prism: Decimal | None = Field(default=None, ge=0, le=20)
    os_prism_base: str | None = Field(default=None, max_length=30)
    os_notes: str | None = Field(default=None, max_length=2000)
    pd_binocular: Decimal | None = None
    pd_right: Decimal | None = None
    pd_left: Decimal | None = None

    @field_validator(*POWER_FIELDS)
    @classmethod
    def validate_power(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        settings = get_settings()
        if not settings.optical_power_min <= value <= settings.optical_power_max:
            supported_range = f"{settings.optical_power_min} to {settings.optical_power_max}"
            raise ValueError(f"Optical power must be within the supported range: {supported_range}")
        if settings.require_quarter_diopter_steps and value % Decimal("0.25"):
            raise ValueError("Optical power must use quarter-diopter increments")
        return value

    @field_validator(*ADD_FIELDS)
    @classmethod
    def validate_add(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        settings = get_settings()
        if not settings.optical_add_min <= value <= settings.optical_add_max:
            raise ValueError(
                f"ADD must be between {settings.optical_add_min} and {settings.optical_add_max}"
            )
        if settings.require_quarter_diopter_steps and value % Decimal("0.25"):
            raise ValueError("ADD must use quarter-diopter increments")
        return value

    @field_validator(*PD_FIELDS)
    @classmethod
    def validate_pd(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        settings = get_settings()
        if not settings.optical_pd_min <= value <= settings.optical_pd_max:
            raise ValueError(
                f"PD must be between {settings.optical_pd_min} and {settings.optical_pd_max} mm"
            )
        return value

    @model_validator(mode="after")
    def validate_dates(self) -> "ExaminationFields":
        if self.expires_on and self.expires_on < date.today():
            raise ValueError("Prescription expiration cannot be in the past")
        return self


class ExaminationCreate(ExaminationFields):
    visit_id: UUID
    examined_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExaminationUpdate(ExaminationFields):
    expected_version: int = Field(ge=1)
    examined_at: datetime | None = None


class ExaminationFinalize(BaseModel):
    expected_version: int = Field(ge=1)


class ExaminationResponse(ExaminationFields):
    id: UUID
    tenant_id: UUID
    examination_number: str
    customer_id: UUID
    customer_name: str
    visit_id: UUID
    examiner_id: UUID
    examiner_name: str
    examined_at: datetime
    status: ExaminationStatus
    finalized_at: datetime | None
    supersedes_id: UUID | None
    revision_number: int
    version: int
    created_at: datetime
    updated_at: datetime


class ComparisonChange(BaseModel):
    field: str
    earlier: Decimal | int | None
    later: Decimal | int | None
    difference: Decimal | int | None


class ExaminationComparison(BaseModel):
    earlier: ExaminationResponse
    later: ExaminationResponse
    changes: list[ComparisonChange]
    notice: str = "Differences are numerical changes only and are not clinical diagnoses."
