"""Add optical examinations and prescription revisions."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_optical_examinations"
down_revision: str | None = "0002_customer_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    exam_status = sa.Enum("DRAFT", "FINALIZED", name="examinationstatus")
    prescription_type = sa.Enum(
        "DISTANCE", "NEAR", "PROGRESSIVE", "OCCUPATIONAL", "OTHER", name="prescriptiontype"
    )
    op.create_table(
        "examinations",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("examination_number", sa.String(24), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("examiner_id", sa.Uuid(), nullable=False),
        sa.Column("examined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", exam_status, nullable=False),
        sa.Column("prescription_type", prescription_type),
        sa.Column("expires_on", sa.Date()),
        sa.Column("notes", sa.Text()),
        sa.Column("od_sphere", sa.Numeric(5, 2)),
        sa.Column("od_cylinder", sa.Numeric(5, 2)),
        sa.Column("od_axis", sa.Integer()),
        sa.Column("od_add", sa.Numeric(4, 2)),
        sa.Column("od_distance_va", sa.String(20)),
        sa.Column("od_near_va", sa.String(20)),
        sa.Column("od_prism", sa.Numeric(4, 2)),
        sa.Column("od_prism_base", sa.String(30)),
        sa.Column("od_notes", sa.Text()),
        sa.Column("os_sphere", sa.Numeric(5, 2)),
        sa.Column("os_cylinder", sa.Numeric(5, 2)),
        sa.Column("os_axis", sa.Integer()),
        sa.Column("os_add", sa.Numeric(4, 2)),
        sa.Column("os_distance_va", sa.String(20)),
        sa.Column("os_near_va", sa.String(20)),
        sa.Column("os_prism", sa.Numeric(4, 2)),
        sa.Column("os_prism_base", sa.String(30)),
        sa.Column("os_notes", sa.Text()),
        sa.Column("pd_binocular", sa.Numeric(5, 2)),
        sa.Column("pd_right", sa.Numeric(5, 2)),
        sa.Column("pd_left", sa.Numeric(5, 2)),
        sa.Column("finalized_at", sa.DateTime(timezone=True)),
        sa.Column("supersedes_id", sa.Uuid()),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["examiner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["examinations.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "examination_number", name="uq_examinations_tenant_number"
        ),
    )
    for column in (
        "tenant_id",
        "examination_number",
        "customer_id",
        "visit_id",
        "examiner_id",
        "examined_at",
        "status",
        "supersedes_id",
    ):
        op.create_index(f"ix_examinations_{column}", "examinations", [column])


def downgrade() -> None:
    op.drop_table("examinations")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="prescriptiontype").drop(bind, checkfirst=True)
        sa.Enum(name="examinationstatus").drop(bind, checkfirst=True)
