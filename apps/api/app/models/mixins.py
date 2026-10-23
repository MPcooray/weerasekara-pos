from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column


class IdMixin:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class TenantMixin:
    tenant_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
