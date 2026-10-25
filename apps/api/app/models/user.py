import enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class UserRole(str, enum.Enum):
    OWNER = "owner"
    MANAGER = "manager"
    OPTOMETRIST = "optometrist"
    CASHIER = "cashier"


CUSTOMER_READ_ROLES = set(UserRole)
CUSTOMER_WRITE_ROLES = set(UserRole)
CUSTOMER_ARCHIVE_ROLES = {UserRole.OWNER, UserRole.MANAGER}
EXAMINATION_FULL_READ_ROLES = {UserRole.OWNER, UserRole.MANAGER, UserRole.OPTOMETRIST}
EXAMINATION_WRITE_ROLES = {UserRole.OWNER, UserRole.OPTOMETRIST}
CATALOG_READ_ROLES = set(UserRole)
INVENTORY_WRITE_ROLES = {UserRole.OWNER, UserRole.MANAGER}
SUPPLIER_WRITE_ROLES = {UserRole.OWNER, UserRole.MANAGER}
CHECKOUT_ROLES = {UserRole.OWNER, UserRole.MANAGER, UserRole.CASHIER}
INVOICE_READ_ROLES = set(UserRole)
PAYMENT_WRITE_ROLES = {UserRole.OWNER, UserRole.MANAGER, UserRole.CASHIER}
QUOTATION_WRITE_ROLES = {UserRole.OWNER, UserRole.MANAGER, UserRole.CASHIER}
RETURN_REQUEST_ROLES = {UserRole.OWNER, UserRole.MANAGER, UserRole.CASHIER}
RETURN_APPROVE_ROLES = {UserRole.OWNER, UserRole.MANAGER}
REFUND_WRITE_ROLES = {UserRole.OWNER, UserRole.MANAGER}
REPORT_READ_ROLES = {UserRole.OWNER, UserRole.MANAGER}
BRANDING_WRITE_ROLES = {UserRole.OWNER, UserRole.MANAGER}
ORDER_READ_ROLES = set(UserRole)
ORDER_WRITE_ROLES = set(UserRole)
ORDER_SUPPLIER_ROLES = {UserRole.OWNER, UserRole.MANAGER}
ORDER_QUALITY_ROLES = {UserRole.OWNER, UserRole.MANAGER, UserRole.OPTOMETRIST}
ORDER_COLLECTION_ROLES = {UserRole.OWNER, UserRole.MANAGER, UserRole.CASHIER}
ORDER_CANCEL_ROLES = {UserRole.OWNER, UserRole.MANAGER}


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),)

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="users")
