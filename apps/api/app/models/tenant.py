from typing import TYPE_CHECKING

from sqlalchemy import String
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

    users: Mapped[list["User"]] = relationship(back_populates="tenant")
