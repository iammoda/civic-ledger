"""Postal-code lookup tests: normalization, MP candidate extraction, matching.

(Sign-in was removed — the platform is fully anonymous. The postal lookup
is the only "who represents me" mechanism and stores nothing.)
"""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.ingestion.sync import SyncContext
from app.main import app
from app.models import Person, PersonMembership
from app.services.represent import extract_mp_candidates, normalize_postal, _match_person


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --- Postal lookup helpers ---


def test_normalize_postal() -> None:
    assert normalize_postal("k1a 0a6") == "K1A0A6"
    assert normalize_postal("K1A-0A6") == "K1A0A6"
    assert normalize_postal("12345") is None
    assert normalize_postal("K1A0A") is None


def test_extract_mp_candidates_dedupes_and_filters() -> None:
    payload = {
        "representatives_centroid": [
            {"elected_office": "MP", "district_name": "Testville", "name": "Jane Doe", "party_name": "Liberal"},
            {"elected_office": "MPP", "district_name": "Testville", "name": "Someone Else"},
        ],
        "representatives_concordance": [
            {"elected_office": "MP", "district_name": "Testville", "name": "Jane Doe", "party_name": "Liberal"},
            {"elected_office": "MP", "district_name": "Otherview", "name": "Bob Roe", "party_name": "NDP"},
        ],
    }
    candidates = extract_mp_candidates(payload)
    assert {c["district_name"] for c in candidates} == {"Testville", "Otherview"}


def test_match_person_by_name_then_riding(db) -> None:
    ctx = SyncContext(db)
    person = Person(slug="jane-doe", full_name="Jane Doe", chamber_id=ctx.house.id)
    db.add(person)
    db.flush()
    db.add(
        PersonMembership(
            person_id=person.id,
            chamber_id=ctx.house.id,
            riding_name="Testville",
            started_on=date(2025, 1, 1),
            is_current=True,
        )
    )
    db.commit()

    assert _match_person(db, "JANE DOE", "Anywhere") == "jane-doe"
    assert _match_person(db, "J. Doe (unmatched name)", "Testville") == "jane-doe"
    assert _match_person(db, "Nobody", "Nowhere") is None


# --- Anonymous surface: /me and /feed are gone ---


def test_me_endpoints_removed(client) -> None:
    assert client.get("/v1/me").status_code in {404, 405}
    assert client.get("/v1/me/feed").status_code in {404, 405}
