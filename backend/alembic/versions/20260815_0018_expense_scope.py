"""Expense items: scope column — federal MP vs Ontario MPP disclosures.

Ontario MPP expenses land in the same expense_items table (same shape,
new categories: accommodation, meals) but must not blend into the federal
explorer by default.

Revision ID: 20260815_0018
Revises: 20260815_0017
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260815_0018"
down_revision = "20260815_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "expense_items",
        sa.Column("scope", sa.String(16), nullable=False, server_default="federal"),
    )
    op.create_index("ix_expense_items_scope", "expense_items", ["scope"])


def downgrade() -> None:
    op.drop_index("ix_expense_items_scope")
    op.drop_column("expense_items", "scope")
