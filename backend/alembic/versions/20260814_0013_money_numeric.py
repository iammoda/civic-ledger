"""Money columns: Float -> Numeric (exact storage and SQL aggregation).

Float summation across millions of contribution/expense rows accumulates
real error — on a platform whose brand is exact receipts, money is stored
as NUMERIC. ORM keeps asdecimal=False so Python-side behavior is unchanged.

Revision ID: 20260814_0013
Revises: 20260814_0012
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260814_0013"
down_revision = "20260814_0012"
branch_labels = None
depends_on = None

MONEY_COLUMNS = [
    ("contributions", "amount", sa.Numeric(14, 2)),
    ("expense_summaries", "salaries", sa.Numeric(14, 2)),
    ("expense_summaries", "travel", sa.Numeric(14, 2)),
    ("expense_summaries", "hospitality", sa.Numeric(14, 2)),
    ("expense_summaries", "contracts", sa.Numeric(14, 2)),
    ("expense_items", "amount", sa.Numeric(14, 2)),
    ("llm_usage", "cost_usd", sa.Numeric(12, 6)),
]


def upgrade() -> None:
    for table, column, money_type in MONEY_COLUMNS:
        op.alter_column(
            table,
            column,
            type_=money_type,
            existing_type=sa.Float(),
            postgresql_using=f"{column}::numeric",
        )


def downgrade() -> None:
    for table, column, _money_type in MONEY_COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.Float(),
            existing_type=sa.Numeric(),
            postgresql_using=f"{column}::double precision",
        )
