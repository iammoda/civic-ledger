"""Issues API tests: topic list counts + per-topic bills and party positions."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.data.topics import seed_topics
from app.db.session import get_db
from app.ingestion.sync import SyncContext
from app.main import app
from app.models import AnalysisResult, Ballot, Bill, EntityTopic, Person, Topic, Vote


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _setup_topic_with_bill_and_vote(db):
    """One climate bill tagged to the topic, one vote, two party ballots."""
    seed_topics(db)
    ctx = SyncContext(db)
    session = ctx.session_for_label("45-1")
    liberal = ctx.party_for_names("Liberal Party of Canada", "Liberal")
    conservative = ctx.party_for_names("Conservative Party of Canada", "Conservative")

    bill = Bill(
        session_id=session.id, chamber_id=ctx.house.id, number="C-12",
        short_title_en="Net-Zero Accountability Act",
        title_en="An Act respecting transparency and accountability in emissions targets",
        introduced_on=date(2026, 2, 1),
    )
    db.add(bill)
    db.flush()

    topic = db.query(Topic).filter(Topic.slug == "climate-environment").one()
    db.add(EntityTopic(topic_id=topic.id, entity_type="bill", entity_id=bill.id, source="manual"))
    db.add(
        AnalysisResult(
            bill_id=bill.id, analysis_type="plain_summary", status="published",
            payload={"one_sentence": "Requires the government to set and report on emissions targets."},
        )
    )

    vote = Vote(
        session_id=session.id, chamber_id=ctx.house.id, number="1",
        occurred_on=date(2026, 3, 1), description_en="2nd reading of Bill C-12",
        bill_id=bill.id, result="Passed",
    )
    db.add(vote)
    db.flush()

    for slug, party_slug, ballot in [
        ("lib-mp", "liberal", "yea"),
        ("con-mp", "conservative", "nay"),
    ]:
        person = Person(slug=slug, full_name=slug.replace("-", " ").title(), chamber_id=ctx.house.id)
        db.add(person)
        db.flush()
        db.add(Ballot(vote_id=vote.id, person_id=person.id, ballot=ballot, party_slug=party_slug))
    db.commit()
    assert liberal is not None and conservative is not None
    return bill


def test_issues_list_counts(db, client) -> None:
    _setup_topic_with_bill_and_vote(db)

    payload = client.get("/v1/issues").json()
    by_slug = {item["slug"]: item for item in payload["items"]}
    assert "climate-environment" in by_slug

    climate = by_slug["climate-environment"]
    assert climate["name_en"] == "Climate & Environment"
    assert climate["bill_count"] == 1
    assert climate["law_count"] == 0
    assert climate["dead_count"] == 0
    # An untouched topic reports zero, not an error.
    assert by_slug["housing"]["bill_count"] == 0


def test_issue_detail_bills_and_party_positions(db, client) -> None:
    _setup_topic_with_bill_and_vote(db)

    detail = client.get("/v1/issues/climate-environment").json()
    assert detail["slug"] == "climate-environment"
    assert detail["vote_count"] == 1
    assert "1 votes" in detail["positions_note"]

    assert len(detail["bills"]) == 1
    bill = detail["bills"][0]
    assert bill["number"] == "C-12"
    assert bill["session"] == "45-1"
    assert bill["short_title_en"] == "Net-Zero Accountability Act"
    assert bill["one_sentence"] == "Requires the government to set and report on emissions targets."

    positions = {p["party_slug"]: p for p in detail["party_positions"]}
    assert positions["liberal"]["yea"] == 1
    assert positions["liberal"]["nay"] == 0
    assert positions["liberal"]["party_name"] == "Liberal Party of Canada"
    assert positions["conservative"]["yea"] == 0
    assert positions["conservative"]["nay"] == 1

    # The receipts: the actual recorded votes behind the party-position bars.
    assert len(detail["votes"]) == 1
    counted = detail["votes"][0]
    assert counted["number"] == "1"
    assert counted["session"] == "45-1"
    assert counted["chamber"] == "house"
    assert counted["bill_number"] == "C-12"
    assert counted["result"] == "Passed"
    assert counted["occurred_on"] == "2026-03-01"


def test_issue_detail_404(db, client) -> None:
    seed_topics(db)
    assert client.get("/v1/issues/not-a-topic").status_code == 404
