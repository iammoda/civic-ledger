"""Toronto/Vancouver open-data vote adapters: grouping + idempotency."""
from __future__ import annotations


from app.ingestion.toronto_votes import sync_toronto_votes
from app.ingestion.vancouver_votes import sync_vancouver_votes
from app.models import Ballot, Chamber, Jurisdiction, Person, Vote


def _council(db, code: str, names: list[str]):
    jur = Jurisdiction(code=code, name_en=code, level="municipal")
    db.add(jur)
    db.flush()
    chamber = Chamber(jurisdiction_id=jur.id, slug="council", name_en=code)
    db.add(chamber)
    db.flush()
    for name in names:
        db.add(
            Person(
                slug=f"{code}-{name.lower().replace(' ', '-')}",
                full_name=name,
                chamber_id=chamber.id,
                source_system="represent",
            )
        )
    db.commit()


TORONTO_ROWS = [
    {
        "Term": "2022-2026", "First Name": "Paul", "Last Name": "Ainslie",
        "Committee": "City Council", "Date/Time": "2022-11-23 15:17 PM",
        "Agenda Item #": "2023.FM1.8", "Agenda Item Title": "Election of the Speaker",
        "Motion Type": "Nomination of a Member", "Vote": "Yes", "Result": "Carried, 25-1",
        "Vote Description": "Majority required",
    },
    {
        "Term": "2022-2026", "First Name": "Gord", "Last Name": "Perks",
        "Committee": "City Council", "Date/Time": "2022-11-23 15:17 PM",
        "Agenda Item #": "2023.FM1.8", "Agenda Item Title": "Election of the Speaker",
        "Motion Type": "Nomination of a Member", "Vote": "No", "Result": "Carried, 25-1",
        "Vote Description": "Majority required",
    },
    # Duplicate member-row (same person, same vote event) must not crash.
    {
        "Term": "2022-2026", "First Name": "Gord", "Last Name": "Perks",
        "Committee": "City Council", "Date/Time": "2022-11-23 15:17 PM",
        "Agenda Item #": "2023.FM1.8", "Agenda Item Title": "Election of the Speaker",
        "Motion Type": "Nomination of a Member", "Vote": "No", "Result": "Carried, 25-1",
        "Vote Description": "Majority required",
    },
]


def test_toronto_grouping_and_idempotency(db):
    _council(db, "toronto-city-council", ["Paul Ainslie", "Gord Perks"])
    for _ in range(2):
        counts = sync_toronto_votes(db, TORONTO_ROWS)
    assert db.query(Vote).count() == 1
    assert db.query(Ballot).count() == 2
    vote = db.query(Vote).one()
    assert vote.yea_total == 1 and vote.nay_total == 1
    assert vote.result == "Passed"
    assert "Election of the Speaker" in vote.description_en
    assert counts["skipped"] == 1  # Second run skips the unchanged group.


VANCOUVER_ROWS = [
    {
        "meeting_type": "Council", "vote_date": "2026-04-21", "vote_number": "11541",
        "agenda_description": "Short Term Rental application",
        "council_member": "Councillor B Montague", "vote": "In Favour", "decision": "Carried Unanimously",
    },
    {
        "meeting_type": "Council", "vote_date": "2026-04-21", "vote_number": "11541",
        "agenda_description": "Short Term Rental application",
        "council_member": "Mayor Ken Sim", "vote": "Opposed", "decision": "Carried Unanimously",
    },
]


def test_vancouver_grouping(db):
    _council(db, "vancouver-city-council", ["Brian Montague", "Ken Sim"])
    counts = sync_vancouver_votes(db, VANCOUVER_ROWS)
    assert counts["votes"] == 1
    ballots = {b.person.full_name: b.ballot for b in db.query(Ballot).all()}
    # "Councillor B Montague" (initial form) and "Mayor Ken Sim" both match.
    assert ballots == {"Brian Montague": "yea", "Ken Sim": "nay"}


def test_unmatched_members_are_counted_not_guessed(db):
    _council(db, "toronto-city-council", ["Paul Ainslie"])  # No Gord Perks.
    counts = sync_toronto_votes(db, TORONTO_ROWS)
    assert counts["unmatched"] == 1
    assert db.query(Ballot).count() == 1
