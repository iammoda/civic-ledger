"""Tier-0 enrichment: bill full text + official Library of Parliament
summaries + FTS index."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260812_0009"
down_revision = "20260811_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bills", sa.Column("official_summary_en", sa.Text(), nullable=True))
    op.add_column("bills", sa.Column("full_text_en", sa.Text(), nullable=True))
    # Generated tsvector over everything searchable about a bill.
    op.execute(
        """
        ALTER TABLE bills ADD COLUMN search_tsv tsvector
        GENERATED ALWAYS AS (
          setweight(to_tsvector('english', coalesce(number, '')), 'A') ||
          setweight(to_tsvector('english', coalesce(short_title_en, '')), 'A') ||
          setweight(to_tsvector('english', coalesce(title_en, '')), 'B') ||
          setweight(to_tsvector('english', coalesce(official_summary_en, '')), 'B') ||
          setweight(to_tsvector('english', left(coalesce(full_text_en, ''), 200000)), 'D')
        ) STORED
        """
    )
    op.execute("CREATE INDEX ix_bills_search_tsv ON bills USING gin (search_tsv)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_bills_search_tsv")
    op.execute("ALTER TABLE bills DROP COLUMN IF EXISTS search_tsv")
    op.drop_column("bills", "full_text_en")
    op.drop_column("bills", "official_summary_en")
