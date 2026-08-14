"""Transparency endpoints + municipal record endpoint."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models import (
    Chamber,
    IngestionRun,
    Jurisdiction,
    Meeting,
    MeetingAttendance,
    Motion,
    Person,
)


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_transparency_status_shows_latest_run_including_failures(db, client):
    db.add(IngestionRun(source_name="escribe", job_name="municipal_sync", status="failed", error_message="boom"))
    db.add(IngestionRun(source_name="escribe", job_name="municipal_sync", status="succeeded", item_count=42))
    db.commit()

    payload = client.get("/v1/transparency/status").json()
    jobs = {j["job"]: j for j in payload["jobs"]}
    assert jobs["municipal_sync"]["status"] == "succeeded"
    assert jobs["municipal_sync"]["item_count"] == 42


def test_transparency_coverage_merges_live_counts(db, client):
    jur = Jurisdiction(code="mississauga-city-council", name_en="Mississauga City Council", level="municipal")
    db.add(jur)
    db.flush()
    chamber = Chamber(jurisdiction_id=jur.id, slug="council", name_en="Mississauga City Council")
    db.add(chamber)
    db.flush()
    db.add(Person(slug="m-kovac", full_name="John Kovac", chamber_id=chamber.id))
    meeting = Meeting(
        chamber_id=chamber.id, body_name="Council", meeting_date=date(2026, 5, 13),
        source_id="mississauga:x", minutes_parsed=True,
    )
    db.add(meeting)
    db.commit()

    payload = client.get("/v1/transparency/coverage").json()
    entry = next(e for e in payload["scorecard"] if e["jurisdiction_code"] == "mississauga-city-council")
    assert entry["live"]["people"] == 1
    assert entry["live"]["meetings"] == 1
    assert payload["honest_limits"]  # The limits section is never empty.


def test_municipal_record_endpoint(db, client):
    jur = Jurisdiction(code="mississauga-city-council", name_en="Mississauga City Council", level="municipal")
    db.add(jur)
    db.flush()
    chamber = Chamber(jurisdiction_id=jur.id, slug="council", name_en="Mississauga City Council")
    db.add(chamber)
    db.flush()
    person = Person(slug="m-kovac", full_name="John Kovac", chamber_id=chamber.id)
    db.add(person)
    db.flush()
    meeting = Meeting(
        chamber_id=chamber.id, body_name="Council", meeting_date=date(2026, 5, 13),
        source_id="mississauga:x", minutes_parsed=True, minutes_url="https://example.com/m",
    )
    db.add(meeting)
    db.flush()
    db.add(MeetingAttendance(meeting_id=meeting.id, person_id=person.id, status="present"))
    db.add(
        Motion(
            meeting_id=meeting.id, sequence=1, resolution_number="0100-2026",
            text_en="Approve the thing", mover_person_id=person.id, result="carried",
            source_url="https://example.com/m",
        )
    )
    db.commit()

    payload = client.get("/v1/politicians/m-kovac/municipal").json()
    assert payload["attendance_pct"] == 100.0
    assert payload["motions_moved"] == 1
    assert payload["recent_motions"][0]["resolution_number"] == "0100-2026"
    assert payload["recent_motions"][0]["source_url"] == "https://example.com/m"
    assert payload["attendance"][0]["body_name"] == "Council"
