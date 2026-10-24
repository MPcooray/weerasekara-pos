from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Tenant(IdMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    default_currency: Mapped[str] = mapped_column(String(3), default="LKR", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    business_display_name: Mapped[str | None] = mapped_column(String(160))
    business_address: Mapped[str | None] = mapped_column(Text)
    business_contact: Mapped[str | None] = mapped_column(String(240))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    invoice_footer: Mapped[str | None] = mapped_column(String(500))
    receipt_footer: Mapped[str | None] = mapped_column(String(500))
    business_registration: Mapped[str | None] = mapped_column(String(120))
    tax_registration: Mapped[str | None] = mapped_column(String(120))

    users: Mapped[list["User"]] = relationship(back_populates="tenant")
