"""Phase 5 tests: petition parsing, upserts, API filters, search integration."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.data.topics import seed_topics
from app.db.session import get_db
from app.ingestion.petitions import (
    parse_deadline,
    parse_petition_text,
    parse_search_rows,
    upsert_petition_row,
)
from app.ingestion.sync import SyncContext
from app.main import app
from app.models import EntityTopic, Person, Petition, Topic
from app.services.search import keyword_search

FIXTURE = (Path(__file__).parent / "fixtures" / "petitions_search.html").read_text()


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --- Parsing (real captured HTML) ---


def test_parse_search_rows_real_fixture() -> None:
    rows = parse_search_rows(FIXTURE)
    assert len(rows) == 3
    by_number = {row["number"]: row for row in rows}
    assert set(by_number) == {"e-7601", "e-7593", "e-7655"}

    row = by_number["e-7593"]
    assert row["title"] == "Indigenous affairs"
    assert row["state"] == "open"
    assert row["closes_at"] == date(2026, 12, 8)
    assert row["sponsor_name"] == "Leah Gazan"
    assert row["signature_count"] == 12
    # Truncated keyword recovered from the title attribute.
    assert any("C-37" in kw and "..." not in kw for kw in row["keywords"])
    assert "Drinking water" in row["keywords"]


def test_parse_deadline_variants() -> None:
    assert parse_deadline("Open for signature until December 9, 2026, at 10:32 a.m. (EDT)") == date(2026, 12, 9)
    assert parse_deadline("Closed for signature") is None


def test_parse_petition_text() -> None:
    html = """
    <div class="pet-details-text"><div class="pet-prayer">
    <h3>Petition to the House of Commons</h3>
    <div>Whereas:</div>
    <ul class="whereas"><li>Wildfires are getting worse;</li></ul>
    </div></div>
    """
    text = parse_petition_text(html)
    assert "Whereas:" in text
    assert "Wildfires are getting worse;" in text
    assert parse_petition_text("<div>no petition here</div>") is None


# --- Upserts ---


def test_upsert_is_idempotent_and_tracks_changes(db) -> None:
    rows = parse_search_rows(FIXTURE)
    for row in rows:
        petition, unchanged = upsert_petition_row(db, row)
        assert unchanged is False  # New rows are changes.
    db.commit()
    assert len(db.scalars(select(Petition)).all()) == 3

    # Re-run: same data -> unchanged; signature bump -> changed.
    _, unchanged = upsert_petition_row(db, rows[0])
    assert unchanged is True
    bumped = {**rows[0], "signature_count": rows[0]["signature_count"] + 5}
    petition, unchanged = upsert_petition_row(db, bumped)
    assert unchanged is False
    assert petition.signature_count == bumped["signature_count"]
    assert len(db.scalars(select(Petition)).all()) == 3


def test_sponsor_matched_to_person(db) -> None:
    ctx = SyncContext(db)
    mp = Person(slug="leah-gazan", full_name="Leah Gazan", chamber_id=ctx.house.id)
    db.add(mp)
    db.commit()

    rows = parse_search_rows(FIXTURE)
    row = next(r for r in rows if r["number"] == "e-7593")
    petition, _ = upsert_petition_row(db, row)
    assert petition.sponsor_person_id == mp.id


# --- API ---


def test_petitions_api_filters(db, client) -> None:
    seed_topics(db)
    rows = parse_search_rows(FIXTURE)
    for row in rows:
        petition, _ = upsert_petition_row(db, row)
    # Manually tag e-7601 with a topic.
    petition = db.scalar(select(Petition).where(Petition.number == "e-7601"))
    housing = db.scalar(select(Topic).where(Topic.slug == "public-safety"))
    db.add(EntityTopic(topic_id=housing.id, entity_type="petition", entity_id=petition.id, source="alias"))
    db.commit()

    all_response = client.get("/v1/petitions").json()
    assert all_response["meta"]["total"] == 3
    first = all_response["items"][0]
    assert first["state"] == "open"
    assert first["sign_url"].startswith("https://www.ourcommons.ca/petitions/en/Petition/Details")
    assert isinstance(first["days_left"], int)

    open_only = client.get("/v1/petitions", params={"state": "open"}).json()
    assert open_only["meta"]["total"] == 3

    by_topic = client.get("/v1/petitions", params={"topic": "public-safety"}).json()
    assert by_topic["meta"]["total"] == 1
    assert by_topic["items"][0]["number"] == "e-7601"
    assert "Public Safety & Crime" in by_topic["items"][0]["topics"]

    unknown_topic = client.get("/v1/petitions", params={"topic": "nope"}).json()
    assert unknown_topic["meta"]["total"] == 0


# --- Search integration ---


def test_petitions_appear_in_keyword_search(db) -> None:
    rows = parse_search_rows(FIXTURE)
    for row in rows:
        upsert_petition_row(db, row)
    db.commit()

    results = keyword_search(db, "drinking water first nations")
    petition_hits = [r for r in results if r.entity_type == "petition"]
    assert petition_hits
    assert petition_hits[0].url_path.startswith("https://")  # External sign link.
