"""Shared test fixtures: in-memory SQLite DB with the non-pgvector tables."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Embedding
from app.models.base import Base


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    # Embedding needs pgvector; exclude it from SQLite test schema.
    tables = [t for name, t in Base.metadata.tables.items() if name != "embeddings"]
    Base.metadata.create_all(engine, tables=tables)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()
