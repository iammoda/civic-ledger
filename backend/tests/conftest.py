"""Shared test fixtures: in-memory SQLite DB with the non-pgvector tables."""
from __future__ import annotations

import os

# Isolate tests from the developer machine: never share a live Redis
# (rate-limit counters / Ask cache), and keep inbound limits out of the way
# except in the tests that exercise them directly.
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:1/0")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("ASK_CACHE_TTL_SECONDS", "0")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Embedding
from app.models.base import Base


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},  # TestClient uses threads
        poolclass=StaticPool,
    )
    # Embedding needs pgvector; exclude it from SQLite test schema.
    tables = [t for name, t in Base.metadata.tables.items() if name != "embeddings"]
    Base.metadata.create_all(engine, tables=tables)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()
