import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.user import User
    from app.models.visit import Visit


class ExaminationStatus(str, enum.Enum):
    DRAFT = "draft"
    FINALIZED = "finalized"


class PrescriptionType(str, enum.Enum):
    DISTANCE = "distance"
    NEAR = "near"
    PROGRESSIVE = "progressive"
    OCCUPATIONAL = "occupational"
    OTHER = "other"


class Examination(IdMixin, TimestampMixin, Base):
    __tablename__ = "examinations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "examination_number", name="uq_examinations_tenant_number"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    examination_number: Mapped[str] = mapped_column(String(24), index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    visit_id: Mapped[UUID] = mapped_column(ForeignKey("visits.id"), index=True)
    examiner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    examined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[ExaminationStatus] = mapped_column(Enum(ExaminationStatus), index=True)
    prescription_type: Mapped[PrescriptionType | None] = mapped_column(Enum(PrescriptionType))
    expires_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    od_sphere: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    od_cylinder: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    od_axis: Mapped[int | None] = mapped_column(Integer)
    od_add: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    od_distance_va: Mapped[str | None] = mapped_column(String(20))
    od_near_va: Mapped[str | None] = mapped_column(String(20))
    od_prism: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    od_prism_base: Mapped[str | None] = mapped_column(String(30))
    od_notes: Mapped[str | None] = mapped_column(Text)

    os_sphere: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    os_cylinder: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    os_axis: Mapped[int | None] = mapped_column(Integer)
    os_add: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    os_distance_va: Mapped[str | None] = mapped_column(String(20))
    os_near_va: Mapped[str | None] = mapped_column(String(20))
    os_prism: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    os_prism_base: Mapped[str | None] = mapped_column(String(30))
    os_notes: Mapped[str | None] = mapped_column(Text)

    pd_binocular: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    pd_right: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    pd_left: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_id: Mapped[UUID | None] = mapped_column(ForeignKey("examinations.id"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer, default=1)

    customer: Mapped["Customer"] = relationship(foreign_keys=[customer_id])
    visit: Mapped["Visit"] = relationship(foreign_keys=[visit_id])
    examiner: Mapped["User"] = relationship(foreign_keys=[examiner_id])
    supersedes: Mapped["Examination | None"] = relationship(remote_side="Examination.id")
