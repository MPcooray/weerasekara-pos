from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import IdMixin, TimestampMixin


class AuditLog(IdMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_id: Mapped[UUID] = mapped_column(index=True)
