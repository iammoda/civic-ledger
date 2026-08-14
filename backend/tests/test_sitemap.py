"""Sitemap endpoint: every indexable path, for the frontend sitemap.xml."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.ingestion.sync import SyncContext
from app.main import app
from app.models import Bill, Person, Vote


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_sitemap_paths_cover_people_bills_and_votes(db, client):
    ctx = SyncContext(db)
    session = ctx.session_for_label("45-1")
    db.add(Person(slug="jane-doe", full_name="Jane Doe"))
    db.add(
        Bill(
            session_id=session.id,
            chamber_id=ctx.house.id,
            number="C-1",
            title_en="An Act",
            outcome="pending",
        )
    )
    db.add(
        Vote(
            session_id=session.id,
            chamber_id=ctx.house.id,
            number="7",
            occurred_on=date(2026, 5, 1),
            description_en="2nd reading",
            result="Passed",
            yea_total=170,
            nay_total=150,
        )
    )
    db.commit()

    paths = client.get("/v1/sitemap-paths").json()["paths"]
    assert "/politicians/jane-doe" in paths
    assert "/bills/45-1/C-1" in paths
    assert "/votes/house/45-1/7" in paths


def test_sitemap_paths_empty_db_is_fine(db, client):
    assert client.get("/v1/sitemap-paths").json()["paths"] == []
