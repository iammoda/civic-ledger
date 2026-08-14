"""Postgres-only search paths: FTS over the search_tsv generated column,
tsquery building, and pgvector cosine search.

These are the *production* code paths that the SQLite suite can't reach.
They run only when PG_TEST_DATABASE_URL points at a migrated Postgres
(CI spins one up and runs `alembic upgrade head` first; locally:

    PG_TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/civic_test \\
        pytest backend/tests/test_search_postgres.py
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PG_URL = os.environ.get("PG_TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not PG_URL, reason="Postgres integration tests need PG_TEST_DATABASE_URL"
)


@pytest.fixture()
def pgdb():
    """Session on the migrated Postgres test DB; everything rolls back."""
    engine = create_engine(PG_URL, future=True)
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, future=True)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def _seed_bill(db, *, number="C-1", title="An Act respecting affordable housing supply", summary=None):
    from app.ingestion.sync import SyncContext
    from app.models import Bill

    ctx = SyncContext(db)
    session = ctx.session_for_label("45-1")
    bill = Bill(
        session_id=session.id,
        chamber_id=ctx.house.id,
        number=number,
        title_en=title,
        official_summary_en=summary,
        outcome="pending",
    )
    db.add(bill)
    db.flush()
    return bill


def test_fts_finds_bill_via_generated_tsv(pgdb):
    """search_tsv is a migration-only generated column — the exact thing a
    create_all() database would silently lack."""
    from app.services.search import keyword_search

    bill = _seed_bill(pgdb)
    results = keyword_search(pgdb, "affordable housing")
    assert any(r.entity_type == "bill" and r.entity_id == bill.id for r in results)


def test_fts_matches_official_summary_text(pgdb):
    from app.services.search import keyword_search

    bill = _seed_bill(
        pgdb,
        number="C-2",
        title="An Act to amend certain Acts",
        summary="This enactment regulates grocery price transparency for consumers.",
    )
    results = keyword_search(pgdb, "grocery prices")
    assert any(r.entity_type == "bill" and r.entity_id == bill.id for r in results)


def test_fts_hyphen_and_stopword_queries_do_not_error(pgdb):
    from app.services.search import keyword_search

    _seed_bill(pgdb)
    # Historical 500: trailing-hyphen tokens broke to_tsquery.
    assert isinstance(keyword_search(pgdb, "co- op housing-"), list)
    # All-stopword query returns empty, not an error.
    assert keyword_search(pgdb, "the and for") == []


def test_vector_search_returns_hydrated_results(pgdb):
    from app.models import Embedding
    from app.services.search import vector_search

    bill = _seed_bill(pgdb)
    vector = [0.0] * 1536
    vector[0] = 1.0
    pgdb.add(
        Embedding(
            entity_type="bill",
            entity_id=bill.id,
            content_hash="x" * 64,
            model_name="text-embedding-3-small",
            vector=vector,
        )
    )
    pgdb.flush()

    results = vector_search(pgdb, vector, limit=5)
    assert results and results[0].entity_type == "bill" and results[0].entity_id == bill.id
    assert results[0].url_path == "/bills/45-1/C-1"


def test_hybrid_search_end_to_end_without_embedding_key(pgdb):
    """hybrid_search on Postgres: keyword phase + graceful no-embedding path."""
    import asyncio

    from app.services.search import hybrid_search

    bill = _seed_bill(pgdb)
    results = asyncio.run(hybrid_search(pgdb, "affordable housing", limit=10))
    assert any(r.entity_type == "bill" and r.entity_id == bill.id for r in results)


def test_migrations_produced_search_tsv_column(pgdb):
    from sqlalchemy import text

    column = pgdb.execute(
        text(
            "SELECT is_generated FROM information_schema.columns "
            "WHERE table_name = 'bills' AND column_name = 'search_tsv'"
        )
    ).scalar()
    assert column == "ALWAYS"


def test_db_is_alembic_versioned(pgdb):
    """The test DB was provisioned by migrations, not create_all()."""
    from sqlalchemy import text

    version = pgdb.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version  # any head; the generated-column test pins the behavior
