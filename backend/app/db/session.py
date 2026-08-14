from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


settings = get_settings()

engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
    # JIT compilation is a net loss for this workload: Postgres re-JITs the
    # pgvector cosine + tsquery expressions on fresh plans (~1.8s per search
    # measured on real data) to "optimize" queries that run in milliseconds.
    # Standard practice for pgvector apps is jit=off per connection.
    connect_args={"options": "-c jit=off"},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

# NOTE: schema provisioning is Alembic-only ("alembic upgrade head").
# A create_all() path would silently miss migration-only DDL (e.g. the
# bills.search_tsv generated column that powers /search).


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
