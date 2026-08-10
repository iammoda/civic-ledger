"""Phase 2: intelligence layer — cost ledger + glossary."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260810_0003"
down_revision = "20260810_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("job_name", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_llm_usage_model_name", "llm_usage", ["model_name"])
    op.create_index("ix_llm_usage_job_name", "llm_usage", ["job_name"])
    op.create_index("ix_llm_usage_created_at", "llm_usage", ["created_at"])

    op.create_table(
        "glossary_terms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("term", sa.String(length=128), nullable=False),
        sa.Column("definition_en", sa.Text(), nullable=False),
        sa.Column("definition_fr", sa.Text(), nullable=True),
        sa.Column("reading_grade", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("term"),
    )
    op.create_index("ix_glossary_terms_term", "glossary_terms", ["term"])


def downgrade() -> None:
    op.drop_table("glossary_terms")
    op.drop_table("llm_usage")
