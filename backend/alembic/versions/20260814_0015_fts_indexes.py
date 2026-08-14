"""GIN expression indexes for the non-bill FTS scans.

Bills got an indexed generated column in 0009; votes/petitions/motions were
still sequential-scanning to_tsvector() on every search (~1.3s per query on
real data, x2 passes per search). These indexes match the exact expressions
keyword_search() builds, cutting each pass to milliseconds.

Revision ID: 20260814_0015
Revises: 20260814_0014
"""
from __future__ import annotations

from alembic import op

revision = "20260814_0015"
down_revision = "20260814_0014"
branch_labels = None
depends_on = None

INDEXES = [
    (
        "ix_votes_description_fts",
        "votes",
        "to_tsvector('english', description_en)",
    ),
    (
        "ix_petitions_text_fts",
        "petitions",
        "to_tsvector('english', title_en || ' ' || coalesce(keywords_en, '') || ' ' || coalesce(text_en, ''))",
    ),
    (
        "ix_motions_text_fts",
        "motions",
        "to_tsvector('english', coalesce(item_title, '') || ' ' || coalesce(text_en, ''))",
    ),
]


def upgrade() -> None:
    for name, table, expression in INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} USING gin ({expression})")


def downgrade() -> None:
    for name, _table, _expression in INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
