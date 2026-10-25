import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import IdMixin


class ProductImportMode(str, enum.Enum):
    CREATE_ONLY = "create_only"
    UPDATE_EXISTING = "update_existing"


class ProductImportStatus(str, enum.Enum):
    PREVIEWED = "previewed"
    COMPLETED = "completed"
    FAILED = "failed"


class ProductImport(IdMixin, Base):
    __tablename__ = "product_imports"
    __table_args__ = (
        UniqueConstraint("tenant_id", "confirmation_key", name="uq_product_import_confirmation"),
    )

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    confirmation_key: Mapped[str | None] = mapped_column(String(100))
    template_version: Mapped[str] = mapped_column(String(20))
    mode: Mapped[ProductImportMode] = mapped_column(Enum(ProductImportMode))
    status: Mapped[ProductImportStatus] = mapped_column(Enum(ProductImportStatus), index=True)
    rows_payload: Mapped[list] = mapped_column(JSON)
    total_rows: Mapped[int] = mapped_column(Integer)
    valid_rows: Mapped[int] = mapped_column(Integer)
    invalid_rows: Mapped[int] = mapped_column(Integer)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    stock_movements_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
