"""pg_trgm indexes for the infix-LIKE search paths.

Site search, the expenses explorer, and per-MP lobbying search all match
with lower(coalesce(col, '')) LIKE '%needle%' — unindexable by btree, so
every request sequential-scanned 100k+ expense rows (~2.7s measured) and
the lobby_communications table. Trigram GIN indexes serve infix LIKE
directly; expressions match exactly what the SQLAlchemy queries emit.

Revision ID: 20260814_0016
Revises: 20260814_0015
"""
from __future__ import annotations

from alembic import op

revision = "20260814_0016"
down_revision = "20260814_0015"
branch_labels = None
depends_on = None

INDEXES = [
    # Expenses explorer + site-search expenses lane.
    ("ix_expense_items_supplier_trgm", "expense_items", "lower(coalesce(supplier, ''))"),
    ("ix_expense_items_description_trgm", "expense_items", "lower(coalesce(description, ''))"),
    ("ix_expense_items_purpose_trgm", "expense_items", "lower(coalesce(purpose, ''))"),
    ("ix_expense_items_city_trgm", "expense_items", "lower(coalesce(city, ''))"),
    ("ix_expense_items_mp_name_trgm", "expense_items", "lower(mp_name_raw)"),
    # Site-search people lane.
    ("ix_people_full_name_trgm", "people", "lower(full_name)"),
    ("ix_person_memberships_riding_trgm", "person_memberships", "lower(coalesce(riding_name, ''))"),
    # Per-MP lobbying search + CSV export.
    ("ix_lobby_comms_client_trgm", "lobby_communications", "lower(coalesce(client_name, ''))"),
    ("ix_lobby_comms_registrant_trgm", "lobby_communications", "lower(coalesce(registrant_name, ''))"),
    ("ix_lobby_comms_subjects_trgm", "lobby_communications", "lower(coalesce(subjects, ''))"),
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for name, table, expression in INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} USING gin ({expression} gin_trgm_ops)")


def downgrade() -> None:
    for name, _table, _expression in INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
