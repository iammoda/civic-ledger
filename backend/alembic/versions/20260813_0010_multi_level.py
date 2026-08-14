"""Multi-level government: jurisdiction levels + contact offices.

- jurisdictions.level: federal | provincial | municipal (existing rows are federal)
- jurisdictions.code widened (municipal codes are representative-set slugs)
- people.offices_json: constituency/legislature office contact blocks from Represent
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260813_0010"
down_revision = "20260812_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "jurisdictions",
        "code",
        existing_type=sa.String(16),
        type_=sa.String(64),
        existing_nullable=False,
    )
    op.add_column(
        "jurisdictions",
        sa.Column("level", sa.String(16), nullable=False, server_default="federal"),
    )
    op.add_column("people", sa.Column("offices_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("people", "offices_json")
    op.drop_column("jurisdictions", "level")
    op.alter_column(
        "jurisdictions",
        "code",
        existing_type=sa.String(64),
        type_=sa.String(16),
        existing_nullable=False,
    )
