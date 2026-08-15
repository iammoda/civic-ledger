"""Expense pipeline tests: real-fixture parsers, sync, detectors, API."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import get_db
from app.ingestion.expenses import (
    discover_quarters,
    parse_contract_detail,
    parse_hospitality_detail,
    parse_member_rows,
    parse_money,
    parse_summary_csv,
    parse_travel_detail,
)
from app.ingestion.sync import SyncContext
from app.main import app
from app.models import ExpenseItem, ExpenseSummary, IntegrityFlag, Person
from app.services.detectors import (
    detect_big_ticket_items,
    detect_donor_vendor_overlap,
    detect_expense_outliers,
    detect_family_name_vendors,
    detect_vendor_concentration,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --- Parsers (captured real HTML/CSV) ---


def test_parse_money() -> None:
    assert parse_money("$1,604.42") == 1604.42
    assert parse_money(" $0.00 ") == 0.0
    assert parse_money("no money here") is None


def test_discover_quarters() -> None:
    html = 'href="/ProactiveDisclosure/en/members/2025/1?x=1" href="/ProactiveDisclosure/en/members/2024/4?y=2"'
    assert discover_quarters(html) == [(2025, 1), (2024, 4)]


def test_parse_summary_csv_real_shape() -> None:
    csv_text = (
        "Name,Constituency,Caucus,Salaries,Travel,Hospitality,Contracts\n"
        'Vacant,Scarborough Southwest,Liberal,32198.7,0,0,108\n'
        '"Alghabra, Hon. Omar",Mississauga Centre,Liberal,0,0,0,21.44\n'
        '"Doe, Jane",Testville,Conservative,"50,000.10",1200.50,300,4000\n'
    )
    rows = parse_summary_csv(csv_text)
    assert len(rows) == 2  # Vacant skipped.
    assert rows[0]["mp_name_raw"] == "Alghabra, Hon. Omar"
    assert rows[1]["salaries"] == 50000.10
    assert rows[1]["caucus"] == "Conservative"


def test_parse_member_rows_real_fixture() -> None:
    html = (FIXTURES / "expense_quarter.html").read_text()
    members = parse_member_rows(html)
    assert len(members) >= 2
    aboultaif = next(m for m in members if "Aboultaif" in m["mp_name_raw"])
    assert aboultaif["caucus"] == "Conservative"
    assert aboultaif["member_uuid"] == "62393729-8881-4750-88ad-a39ad140b4ad"
    assert set(aboultaif["detail_paths"]) == {"travel", "hospitality", "contract"}
    # Sparse rows (zero-spend categories) only link existing reports.
    aitchison = next(m for m in members if "Aitchison" in m["mp_name_raw"])
    assert "hospitality" not in aitchison["detail_paths"]


def test_parse_contract_detail_real_fixture() -> None:
    html = (FIXTURES / "expense_contract.html").read_text()
    items = parse_contract_detail(html)
    assert len(items) > 10
    first = items[0]
    assert first["supplier"].startswith("Bell Mobility")
    assert first["amount"] == 64.95
    assert first["occurred_on"] == date(2024, 1, 4)
    rental = next(i for i in items if i["description"] == "Office Rental")
    assert rental["amount"] > 1000


def test_parse_hospitality_detail_real_fixture() -> None:
    html = (FIXTURES / "expense_hospitality.html").read_text()
    items = parse_hospitality_detail(html)
    assert items
    # Sub-items carry searchable suppliers inheriting event context.
    sobeys = next((i for i in items if (i.get("supplier") or "").startswith("Sobey")), None)
    assert sobeys is not None
    assert sobeys["amount"] == 23.94
    assert sobeys["occurred_on"] == date(2024, 4, 12)
    assert sobeys["city"] == "Ajax"
    # Event totals are not double-counted as items.
    assert not any((i.get("supplier") or "") == "Total" for i in items)


def test_parse_travel_detail_real_fixture() -> None:
    html = Path("/tmp/travel.html").read_text() if Path("/tmp/travel.html").exists() else None
    if html is None:
        pytest.skip("full travel page not captured")
    items = parse_travel_detail(html)
    assert items
    first = items[0]
    assert first["claim_ref"].startswith("T")
    assert first["amount"] > 0
    # Traveller context attached from the nested table.
    assert any(i["traveller_name"] for i in items)
    assert any((i["traveller_type"] or "").lower() == "member" for i in items)


# --- Detectors ---


def _mp(db, slug="jane-doe", name="Jane Doe", family="Doe") -> Person:
    ctx = SyncContext(db)
    person = Person(slug=slug, full_name=name, family_name=family, chamber_id=ctx.house.id)
    db.add(person)
    db.commit()
    return person


def _summary(db, person, *, caucus="Liberal", fy=2025, q=1, travel=0.0, contracts=0.0, name=None):
    db.add(
        ExpenseSummary(
            person_id=person.id if person else None,
            mp_name_raw=name or (person.full_name if person else "X"),
            caucus=caucus, fiscal_year=fy, quarter=q,
            travel=travel, contracts=contracts,
        )
    )


def _item(db, person, *, category="contract", amount, supplier=None, fy=2025, q=1, seq=0):
    db.add(
        ExpenseItem(
            person_id=person.id,
            mp_name_raw=person.full_name,
            category=category, fiscal_year=fy, quarter=q,
            supplier=supplier, amount=amount,
            source_url="https://www.ourcommons.ca/x",
            fingerprint=f"fp-{person.slug}-{category}-{amount}-{supplier}-{seq}",
        )
    )


def test_expense_outlier_detector(db) -> None:
    jane = _mp(db)
    _summary(db, jane, travel=60000)
    # 20+ House-wide peers around the median (caucus is irrelevant).
    for i in range(22):
        peer = _mp(db, slug=f"peer-{i}", name=f"Peer {i}", family=f"Peer{i}")
        _summary(db, peer, caucus="Conservative" if i % 2 else "Liberal", travel=10000 + i * 200)
    db.commit()

    created = detect_expense_outliers(db)
    assert created == 1
    flag = db.scalar(select(IntegrityFlag))
    assert flag.detector == "expense_outlier"
    assert flag.status == "pending_review"
    assert "House-wide" in flag.headline_en
    assert flag.evidence["ratio"] > 2.5
    assert detect_expense_outliers(db) == 0  # Dedupe.


def test_big_ticket_detector(db) -> None:
    jane = _mp(db)
    _item(db, jane, category="contract", amount=30000, supplier="Big Print Co")
    _item(db, jane, category="contract", amount=500, supplier="Small Shop")
    _item(db, jane, category="hospitality", amount=6000, supplier="Banquet Hall")
    _item(db, jane, category="travel", amount=14000)  # Under travel threshold.
    db.commit()

    created = detect_big_ticket_items(db)
    assert created == 2
    detectors = [f.headline_en for f in db.scalars(select(IntegrityFlag)).all()]
    assert any("Big Print Co" in h for h in detectors)
    assert any("Banquet Hall" in h for h in detectors)


def test_vendor_concentration_detector(db) -> None:
    jane = _mp(db)
    for i in range(5):
        _item(db, jane, amount=5000, supplier="One Vendor Ltd", seq=i)
    _item(db, jane, amount=3000, supplier="Other Co", seq=99)
    db.commit()

    created = detect_vendor_concentration(db)
    assert created == 1
    flag = db.scalar(select(IntegrityFlag).where(IntegrityFlag.detector == "expense_vendor_concentration"))
    assert "One Vendor Ltd" in flag.headline_en
    assert flag.evidence["payment_count"] == 5


def test_family_name_vendor_detector(db) -> None:
    jane = _mp(db, family="Bilbo")
    _item(db, jane, amount=5000, supplier="Bilbo Holdings Ltd.")
    _item(db, jane, amount=5000, supplier="Unrelated Co", seq=1)
    db.commit()

    created = detect_family_name_vendors(db)
    assert created == 1
    flag = db.scalar(select(IntegrityFlag).where(IntegrityFlag.detector == "expense_family_name_vendor"))
    assert "shares the MP's family name" in flag.headline_en
    assert flag.confidence < 0.5  # Explicitly low confidence.


def test_donor_vendor_overlap_detector(db) -> None:
    from app.ingestion.influence import sync_contributions

    jane = _mp(db)
    contrib_csv = (
        "Political entity,Recipient,Political party of recipient,Contributor name,"
        "Contributor's city,Contributor's province,Contribution Received date,Monetary amount\n"
        'Candidate,"Doe, Jane",Liberal,Acme Printing Inc.,Ottawa,ON,2026-01-05,1000.00\n'
    )
    sync_contributions(db, contrib_csv)
    _item(db, jane, amount=2000, supplier="Acme Printing")
    db.commit()

    created = detect_donor_vendor_overlap(db)
    assert created == 1
    flag = db.scalar(select(IntegrityFlag).where(IntegrityFlag.detector == "expense_donor_vendor_overlap"))
    assert "also appears as a contributor" in flag.headline_en


# --- API ---


def test_mp_expenses_endpoint(db, client) -> None:
    jane = _mp(db)
    _summary(db, jane, travel=12000, contracts=8000)
    for i in range(4):
        peer = _mp(db, slug=f"peer-{i}", name=f"Peer {i}")
        _summary(db, peer, travel=9000)
    _item(db, jane, amount=5000, supplier="Big Print Co")
    _item(db, jane, amount=100, supplier="Small Shop", seq=1)
    db.commit()

    data = client.get("/v1/politicians/jane-doe/expenses").json()
    assert data["quarters"][0]["travel"] == 12000
    assert data["quarters"][0]["total"] == 20000
    assert data["top_items"][0]["supplier"] == "Big Print Co"
    assert data["top_suppliers"][0]["supplier"] == "Big Print Co"
    assert data["flags"] == []  # Nothing published without review.
    assert "human-reviewed" in data["sources_note"]


def test_expense_search_filters_and_sort(db, client) -> None:
    jane = _mp(db)
    bob = _mp(db, slug="bob-roe", name="Bob Roe", family="Roe")
    _item(db, jane, amount=5000, supplier="Big Print Co", category="contract")
    _item(db, bob, amount=9000, supplier="Fancy Banquets", category="hospitality")
    _item(db, bob, amount=200, supplier="Big Print Co", category="contract", seq=1)
    db.commit()

    biggest_first = client.get("/v1/expenses/search").json()
    assert biggest_first["meta"]["total"] == 3
    assert biggest_first["items"][0]["amount"] == 9000
    assert biggest_first["items"][0]["mp_slug"] == "bob-roe"

    by_supplier = client.get("/v1/expenses/search", params={"q": "big print"}).json()
    assert by_supplier["meta"]["total"] == 2

    by_category = client.get("/v1/expenses/search", params={"category": "hospitality"}).json()
    assert by_category["meta"]["total"] == 1

    by_min = client.get("/v1/expenses/search", params={"min_amount": 4000}).json()
    assert by_min["meta"]["total"] == 2

    by_mp_name = client.get("/v1/expenses/search", params={"q": "bob roe"}).json()
    assert by_mp_name["meta"]["total"] == 2


def test_expense_csv_export(db, client) -> None:
    jane = _mp(db)
    _item(db, jane, category="contract", amount=30000.0, supplier="Acme Consulting")
    _item(db, jane, category="travel", amount=900.0, supplier="Air Co", seq=1)
    db.commit()

    response = client.get("/v1/expenses/search.csv", params={"category": "contract"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    lines = response.text.strip().splitlines()
    assert lines[0].startswith("fiscal_year,quarter,date,mp_name,category,supplier")
    assert len(lines) == 2  # header + the one contract row
    assert "Acme Consulting" in lines[1]
    assert "30000.00" in lines[1]


def test_expense_search_matches_natural_name_order(db, client) -> None:
    """Names are stored surname-first ('Holland, Hon. Mark') — searching
    'Mark Holland' must still find them (token AND-matching)."""
    mp = _mp(db, slug="mark-holland", name="Holland, Hon. Mark", family="Holland")
    _item(db, mp, category="hospitality", amount=500.0, supplier="Catering Co")
    db.commit()

    for query in ("Mark Holland", "holland mark", "Holland"):
        payload = client.get("/v1/expenses/search", params={"q": query}).json()
        assert payload["meta"]["total"] == 1, f"query {query!r} found nothing"

    # Tokens must ALL match: an unrelated word kills the row.
    payload = client.get("/v1/expenses/search", params={"q": "mark nonexistentword"}).json()
    assert payload["meta"]["total"] == 0

    # Tokens can span fields: name + supplier together.
    payload = client.get("/v1/expenses/search", params={"q": "holland catering"}).json()
    assert payload["meta"]["total"] == 1
