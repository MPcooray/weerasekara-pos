import enum
from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Date, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.visit import Visit


class Gender(str, enum.Enum):
    FEMALE = "female"
    MALE = "male"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class Customer(IdMixin, TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "customer_number", name="uq_customers_tenant_number"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    customer_number: Mapped[str] = mapped_column(String(24), index=True)
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    mobile_number: Mapped[str] = mapped_column(String(24), index=True)
    alternative_contact_number: Mapped[str | None] = mapped_column(String(24))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[Gender | None] = mapped_column(Enum(Gender))
    address: Mapped[str | None] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    is_archived: Mapped[bool] = mapped_column(default=False, index=True)

    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_id])
    visits: Mapped[list["Visit"]] = relationship(
        back_populates="customer", cascade="save-update, merge", order_by="desc(Visit.visit_at)"
    )
