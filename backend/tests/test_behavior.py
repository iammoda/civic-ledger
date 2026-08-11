"""Phase 7 tests: voting record endpoint, party context, comparison."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.behavior import _ballot_effect
from app.db.session import get_db
from app.ingestion.sync import SyncContext
from app.main import app
from app.models import Ballot, Person, PersonMembership, PersonStats, Vote


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _setup_vote_with_party(db):
    """Jane (liberal) + 4 party colleagues; Jane dissents on vote 2."""
    ctx = SyncContext(db)
    session = ctx.session_for_label("45-1")
    party = ctx.party_for_names("Liberal Party of Canada", "Liberal")

    people = []
    for i, slug in enumerate(["jane-doe", "mp-1", "mp-2", "mp-3", "mp-4"]):
        person = Person(slug=slug, full_name=slug.replace("-", " ").title(), chamber_id=ctx.house.id)
        db.add(person)
        db.flush()
        db.add(
            PersonMembership(
                person_id=person.id, party_id=party.id, chamber_id=ctx.house.id,
                started_on=date(2025, 1, 1), is_current=True,
            )
        )
        people.append(person)

    votes = []
    for number, (yea_effect, desc) in enumerate(
        [("advance", "2nd reading and adoption of Bill C-1"), ("advance", "3rd reading of Bill C-1")], start=1
    ):
        vote = Vote(
            session_id=session.id, chamber_id=ctx.house.id, number=str(number),
            occurred_on=date(2026, 5, number), description_en=desc,
            plain_meaning_en="A Yes vote moved this forward.", yea_effect=yea_effect, result="Passed",
        )
        db.add(vote)
        votes.append(vote)
    db.flush()

    # Vote 1: everyone yea. Vote 2: Jane nay (dissent), others yea.
    for vote_index, vote in enumerate(votes):
        for i, person in enumerate(people):
            is_jane = person.slug == "jane-doe"
            ballot_value = "nay" if (vote_index == 1 and is_jane) else "yea"
            db.add(
                Ballot(
                    vote_id=vote.id, person_id=person.id, ballot=ballot_value,
                    party_slug="liberal", broke_party_line=(vote_index == 1 and is_jane),
                )
            )
    db.commit()
    return people[0]


def test_ballot_effect_translation() -> None:
    assert _ballot_effect("yea", "advance") == "advanced"
    assert _ballot_effect("nay", "advance") == "blocked"
    assert _ballot_effect("yea", "block") == "blocked"
    assert _ballot_effect("nay", "block") == "advanced"
    assert _ballot_effect("absent", "advance") is None
    assert _ballot_effect("yea", None) is None


def test_voting_record_with_party_context(db, client) -> None:
    jane = _setup_vote_with_party(db)

    record = client.get(f"/v1/politicians/{jane.slug}/votes").json()
    assert record["total_ballots"] == 2
    assert record["dissent_count"] == 1

    items = {item["vote_number"]: item for item in record["items"]}
    unified = items["1"]
    assert unified["ballot_effect"] == "advanced"
    assert unified["broke_party_line"] is False
    assert unified["party_context"] == "With 5 of 5 voting Liberal MPs"

    dissent = items["2"]
    assert dissent["ballot_effect"] == "blocked"  # Nay on an advancing motion.
    assert dissent["broke_party_line"] is True
    assert dissent["party_context"] == "One of 1 Liberal MPs to vote this way — 4 voted the other way"


def test_voting_record_dissent_filter(db, client) -> None:
    jane = _setup_vote_with_party(db)
    record = client.get(f"/v1/politicians/{jane.slug}/votes", params={"dissent_only": "true"}).json()
    assert len(record["items"]) == 1
    assert record["items"][0]["vote_number"] == "2"


def test_voting_record_404(client) -> None:
    assert client.get("/v1/politicians/nobody/votes").status_code == 404


def test_compare_endpoint(db, client) -> None:
    jane = _setup_vote_with_party(db)
    session_id = db.scalar(select(Vote.session_id).limit(1))
    db.add(
        PersonStats(
            person_id=jane.id, session_id=session_id,
            votes_eligible=2, votes_cast=2, attendance_pct=100.0, party_line_pct=50.0, dissent_count=1,
        )
    )
    db.commit()

    response = client.get("/v1/compare", params={"a": "jane-doe", "b": "mp-1"}).json()
    assert response["a"]["full_name"] == "Jane Doe"
    assert response["a"]["attendance_pct"] == 100.0
    assert response["a"]["dissent_count"] == 1
    assert response["a"]["party"] == "Liberal"
    assert response["b"]["attendance_pct"] is None  # No stats row yet.

    missing = client.get("/v1/compare", params={"a": "jane-doe", "b": "ghost"})
    assert missing.status_code == 404
