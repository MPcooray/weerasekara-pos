"""Add customers, visits, and audit logs."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_customer_management"
down_revision: str | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    gender = sa.Enum("FEMALE", "MALE", "OTHER", "PREFER_NOT_TO_SAY", name="gender")
    visit_status = sa.Enum("OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED", name="visitstatus")
    op.create_table(
        "customers",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("customer_number", sa.String(24), nullable=False),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("mobile_number", sa.String(24), nullable=False),
        sa.Column("alternative_contact_number", sa.String(24)),
        sa.Column("date_of_birth", sa.Date()),
        sa.Column("gender", gender),
        sa.Column("address", sa.String(500)),
        sa.Column("email", sa.String(320)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "customer_number", name="uq_customers_tenant_number"),
    )
    for column in (
        "tenant_id",
        "customer_number",
        "full_name",
        "mobile_number",
        "email",
        "is_archived",
    ):
        op.create_index(f"ix_customers_{column}", "customers", [column])

    op.create_table(
        "visits",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("visit_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("purpose", sa.String(200), nullable=False),
        sa.Column("assigned_staff_id", sa.Uuid()),
        sa.Column("status", visit_status, nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["assigned_staff_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("tenant_id", "customer_id", "visit_at", "assigned_staff_id", "status"):
        op.create_index(f"ix_visits_{column}", "visits", [column])

    op.create_table(
        "audit_logs",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("tenant_id", "actor_id", "action", "entity_type", "entity_id"):
        op.create_index(f"ix_audit_logs_{column}", "audit_logs", [column])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("visits")
    op.drop_table("customers")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="visitstatus").drop(bind, checkfirst=True)
        sa.Enum(name="gender").drop(bind, checkfirst=True)
