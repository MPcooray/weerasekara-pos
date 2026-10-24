"""Replace the reserved local development admin email domain."""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_valid_admin_email"
down_revision: str | None = "0003_optical_examinations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE users SET email = 'owner@weerasekara.lk' WHERE email = 'owner@weerasekara.local'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE users SET email = 'owner@weerasekara.local' WHERE email = 'owner@weerasekara.lk'"
    )
