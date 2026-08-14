"""Ontario (ola.org) ingestion: parsers + idempotent persistence."""
from __future__ import annotations

from datetime import date

from app.ingestion.ontario import (
    OntarioSyncContext,
    normalize_name,
    parse_bill_detail,
    parse_bills_index,
    upsert_ontario_bill,
    upsert_ontario_vote,
)
from app.models import Ballot, Bill, Person, PersonMembership, Vote


INDEX_HTML = """
<table><tbody>
<tr><td>1</td><td>An Act to perpetuate an ancient parliamentary right </td>
  <td> Ford, Hon. Doug  (Premier) </td>
  <td><a href="/en/legislative-business/bills/parliament-44/session-1/bill-1">Bill 1</a></td></tr>
<tr><td>5</td><td>Protect Ontario by Unleashing our Economy Act, 2025 </td>
  <td> Fedeli, Hon. Victor </td>
  <td><a href="/en/legislative-business/bills/parliament-44/session-1/bill-5">Bill 5</a></td></tr>
<tr><td>PR1</td><td>1976998 Ontario Inc. Act, 2025 </td>
  <td> Dixon, Jess </td>
  <td><a href="/en/legislative-business/bills/parliament-44/session-1/bill-pr1">Bill PR1</a></td></tr>
</tbody></table>
"""

DETAIL_HTML = """
<div class="lao-tab-content bill-status-tab">
<table>
<tr><th>Date</th><th>Bill stage</th><th>Event</th><th>Outcome</th></tr>
<tr><td>June 5, 2025</td><td>Royal Assent</td><td>Royal Assent received</td><td>-</td></tr>
<tr><td>June 4, 2025</td><td>Third Reading</td><td>Vote</td><td>Carried on division</td></tr>
<tr><td>April 17, 2025</td><td>First Reading</td><td>Vote</td><td>Carried on division</td></tr>
</table>
</div>
<div class="lao-tab-content bill-votes-tab">
<div class="view-content">
<h2 class="view-grouping-header"> Vote on third reading - Carried (June 4, 2025)</h2>
<div class="view-grouping"><div class="view-grouping-content">
  <h3> Ayes\n  (2)</h3>
  <div class="row">
    <div class="col-6 col-lg-3"> Hon. Victor Fedeli </div>
    <div class="col-6 col-lg-3"> France Gélinas </div>
  </div>
  <h3> Nays\n  (1)</h3>
  <div class="row">
    <div class="col-6 col-lg-3"> Jennifer (Jennie) Stevens </div>
  </div>
</div></div>
</div>
"""


def test_parse_bills_index():
    stubs = parse_bills_index(INDEX_HTML)
    assert [s.number for s in stubs] == ["1", "5", "PR1"]
    assert stubs[1].sponsor_names == ["Victor Fedeli"]
    assert stubs[0].sponsor_names == ["Doug Ford"]
    assert stubs[1].path.endswith("/bill-5")


def test_parse_bill_detail():
    detail = parse_bill_detail(DETAIL_HTML)
    assert detail.status_en == "Royal Assent — Royal Assent received"
    assert detail.introduced_on == date(2025, 4, 17)
    assert detail.received_royal_assent is True
    assert len(detail.divisions) == 1
    division = detail.divisions[0]
    assert division.description == "Vote on third reading"
    assert division.result == "Carried"
    assert division.occurred_on == date(2025, 6, 4)
    assert division.ayes == ["Hon. Victor Fedeli", "France Gélinas"]
    assert division.nays == ["Jennifer (Jennie) Stevens"]


def test_normalize_name():
    assert normalize_name("Hon. France Gélinas") == "france gelinas"
    assert normalize_name("Jennifer (Jennie) Stevens") == "jennifer stevens"


def _seed_mpps(db, ctx):
    """MPPs as the Represent sync would create them."""
    for name in ("Victor Fedeli", "France Gélinas", "Jennifer (Jennie) Stevens"):
        person = Person(
            slug=f"on-{normalize_name(name).replace(' ', '-')}",
            full_name=name,
            chamber_id=ctx.chamber.id,
            source_system="represent",
        )
        db.add(person)
        db.flush()
        db.add(PersonMembership(person_id=person.id, chamber_id=ctx.chamber.id, is_current=True))
    db.commit()


def test_upsert_bill_and_vote_idempotent(db):
    ctx = OntarioSyncContext(db)
    _seed_mpps(db, ctx)
    session = ctx.session_for(44, 1)
    stub = parse_bills_index(INDEX_HTML)[1]
    detail = parse_bill_detail(DETAIL_HTML)

    for _ in range(2):
        bill = upsert_ontario_bill(ctx, session, stub, detail)
        for division in detail.divisions:
            upsert_ontario_vote(ctx, session, bill, division)
        db.commit()

    assert db.query(Bill).count() == 1
    assert db.query(Vote).count() == 1
    assert db.query(Ballot).count() == 3

    bill = db.query(Bill).one()
    assert bill.is_law is True
    assert bill.outcome == "enacted"
    assert bill.introduced_on == date(2025, 4, 17)
    assert bill.sponsor.full_name == "Victor Fedeli"
    assert bill.bill_type == "government"

    vote = db.query(Vote).one()
    assert vote.yea_total == 2
    assert vote.nay_total == 1
    assert vote.result == "Passed"
    assert vote.yea_effect == "advance"
    assert vote.number.startswith("5-vote-on-third-reading-2025-06-04")

    # Name matching handled the Hon. prefix, accents, and nicknames.
    ballots = {b.person.full_name: b.ballot for b in db.query(Ballot).all()}
    assert ballots == {
        "Victor Fedeli": "yea",
        "France Gélinas": "yea",
        "Jennifer (Jennie) Stevens": "nay",
    }
