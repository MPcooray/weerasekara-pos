from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import IdMixin, TimestampMixin


class Supplier(IdMixin, TimestampMixin, Base):
    __tablename__ = "suppliers"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    business_name: Mapped[str] = mapped_column(String(160), index=True)
    contact_person: Mapped[str | None] = mapped_column(String(160))
    telephone: Mapped[str | None] = mapped_column(String(24))
    email: Mapped[str | None] = mapped_column(String(320))
    address: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    is_archived: Mapped[bool] = mapped_column(default=False, index=True)
