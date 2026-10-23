import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.user import User


class VisitStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Visit(IdMixin, TimestampMixin, Base):
    __tablename__ = "visits"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    visit_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    purpose: Mapped[str] = mapped_column(String(200))
    assigned_staff_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[VisitStatus] = mapped_column(Enum(VisitStatus), index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    customer: Mapped["Customer"] = relationship(back_populates="visits")
    assigned_staff: Mapped["User | None"] = relationship(foreign_keys=[assigned_staff_id])
