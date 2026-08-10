"""Phase 4 tests: session auth, postal->MP matching, profile + follows API."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.auth import get_current_user
from app.data.topics import seed_topics
from app.db.session import get_db
from app.ingestion.sync import SyncContext
from app.main import app
from app.models import Person, PersonMembership
from app.services.represent import extract_mp_candidates, normalize_postal, _match_person


AUTH_DDL = [
    'CREATE TABLE "user" (id TEXT PRIMARY KEY, name TEXT, email TEXT, "emailVerified" BOOLEAN, image TEXT, "createdAt" TIMESTAMP, "updatedAt" TIMESTAMP)',
    'CREATE TABLE "session" (id TEXT PRIMARY KEY, "userId" TEXT, token TEXT, "expiresAt" TIMESTAMP, "createdAt" TIMESTAMP, "updatedAt" TIMESTAMP)',
]


def _seed_auth_user(db, *, token: str = "tok123", expired: bool = False) -> None:
    for ddl in AUTH_DDL:
        db.execute(text(ddl))
    expires = datetime.now(timezone.utc) + (timedelta(days=-1) if expired else timedelta(days=7))
    db.execute(
        text('INSERT INTO "user" (id, name, email) VALUES (:i, :n, :e)'),
        {"i": "u1", "n": "Jane Citizen", "e": "jane@example.com"},
    )
    db.execute(
        text('INSERT INTO "session" (id, "userId", token, "expiresAt") VALUES (:i, :u, :t, :x)'),
        {"i": "s1", "u": "u1", "t": token, "x": expires.replace(tzinfo=None)},
    )
    db.commit()


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --- Auth dependency ---


class _FakeRequest:
    def __init__(self, cookies: dict[str, str]) -> None:
        self.cookies = cookies


def test_session_cookie_authenticates(db) -> None:
    _seed_auth_user(db, token="tok123")
    request = _FakeRequest({"better-auth.session_token": "tok123.somesignature"})
    user = get_current_user(request, db)  # type: ignore[arg-type]
    assert user is not None
    assert user.email == "jane@example.com"


def test_expired_session_rejected(db) -> None:
    _seed_auth_user(db, token="tok123", expired=True)
    request = _FakeRequest({"better-auth.session_token": "tok123.sig"})
    assert get_current_user(request, db) is None  # type: ignore[arg-type]


def test_missing_cookie_is_anonymous(db) -> None:
    assert get_current_user(_FakeRequest({}), db) is None  # type: ignore[arg-type]


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


# --- /v1/me API ---


def test_me_requires_auth(client) -> None:
    assert client.get("/v1/me").status_code == 401


def test_profile_and_follows_flow(db, client) -> None:
    _seed_auth_user(db, token="tok123")
    seed_topics(db)
    ctx = SyncContext(db)
    mp = Person(slug="jane-doe", full_name="Jane Doe", chamber_id=ctx.house.id)
    db.add(mp)
    db.commit()

    cookies = {"better-auth.session_token": "tok123.sig"}

    me = client.get("/v1/me", cookies=cookies)
    assert me.status_code == 200
    assert me.json()["profile"]["reading_level"] == "standard"

    updated = client.put(
        "/v1/me/profile",
        json={"riding_name": "Testville", "province_code": "ON", "mp_slug": "jane-doe", "reading_level": "simple"},
        cookies=cookies,
    )
    assert updated.status_code == 200
    profile = updated.json()["profile"]
    assert profile["mp_name"] == "Jane Doe"
    assert profile["reading_level"] == "simple"

    followed = client.post("/v1/me/follows", json={"target_type": "topic", "target_ref": "housing"}, cookies=cookies)
    assert followed.status_code == 201
    follows = followed.json()["follows"]
    assert follows[0]["target_ref"] == "housing"
    assert follows[0]["label"] == "Housing"

    # Duplicate follow is a no-op.
    again = client.post("/v1/me/follows", json={"target_type": "topic", "target_ref": "housing"}, cookies=cookies)
    assert len(again.json()["follows"]) == 1

    # Unknown topic rejected.
    bad = client.post("/v1/me/follows", json={"target_type": "topic", "target_ref": "nonsense"}, cookies=cookies)
    assert bad.status_code == 404

    removed = client.delete(
        "/v1/me/follows",
        params={"target_type": "topic", "target_ref": "housing"},
        cookies=cookies,
    )
    assert removed.json()["follows"] == []


def test_invalid_reading_level_rejected(db, client) -> None:
    _seed_auth_user(db, token="tok123")
    response = client.put(
        "/v1/me/profile",
        json={"reading_level": "genius"},
        cookies={"better-auth.session_token": "tok123.sig"},
    )
    assert response.status_code == 422
