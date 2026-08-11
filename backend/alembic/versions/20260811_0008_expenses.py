"""MP expenses: quarterly summaries + line items (Proactive Disclosure)."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260811_0008"
down_revision = "20260810_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expense_summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("mp_name_raw", sa.String(length=255), nullable=False),
        sa.Column("constituency", sa.String(length=255), nullable=True),
        sa.Column("caucus", sa.String(length=128), nullable=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("quarter", sa.Integer(), nullable=False),
        sa.Column("salaries", sa.Float(), nullable=False, server_default="0"),
        sa.Column("travel", sa.Float(), nullable=False, server_default="0"),
        sa.Column("hospitality", sa.Float(), nullable=False, server_default="0"),
        sa.Column("contracts", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("mp_name_raw", "fiscal_year", "quarter", name="uq_expense_summary_mp_quarter"),
    )
    for col in ("person_id", "mp_name_raw", "caucus", "fiscal_year", "quarter"):
        op.create_index(f"ix_expense_summaries_{col}", "expense_summaries", [col])

    op.create_table(
        "expense_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("mp_name_raw", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("quarter", sa.Integer(), nullable=False),
        sa.Column("supplier", sa.String(length=500), nullable=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("occurred_on", sa.Date(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("traveller_name", sa.String(length=255), nullable=True),
        sa.Column("traveller_type", sa.String(length=64), nullable=True),
        sa.Column("purpose", sa.String(length=500), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("claim_ref", sa.String(length=64), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("fingerprint"),
    )
    for col in (
        "person_id", "mp_name_raw", "category", "fiscal_year", "quarter",
        "supplier", "organization_id", "occurred_on", "amount", "traveller_type", "fingerprint",
    ):
        op.create_index(f"ix_expense_items_{col}", "expense_items", [col])


def downgrade() -> None:
    op.drop_table("expense_items")
    op.drop_table("expense_summaries")
