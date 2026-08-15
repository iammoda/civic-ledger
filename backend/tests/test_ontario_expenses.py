"""Ontario MPP expense disclosures: parsers (real fixtures) + persistence."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.ingestion.ontario_expenses import (
    MemberDisclosure,
    _ontario_mpp_index,
    parse_disclosure_page,
    parse_expense_csv,
    parse_member_slugs,
    persist_member_expenses,
)
from app.models import ExpenseItem

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_member_slugs_real_fixture() -> None:
    slugs = parse_member_slugs((FIXTURES / "ontario_members_current.html").read_text())
    assert len(slugs) >= 100
    assert "deepak-anand" in slugs
    assert all("/" not in slug for slug in slugs)


def test_parse_disclosure_page_real_fixture() -> None:
    disclosure = parse_disclosure_page(
        (FIXTURES / "ontario_mpp_disclosure.html").read_text(), "deepak-anand"
    )
    assert disclosure.csv_url == (
        "https://www.ola.org/sites/default/files/node-files/member/expense-disclosure/expenses-anand-deepak.csv"
    )
    assert disclosure.display_name == "Anand, Deepak"
    assert disclosure.riding == "Mississauga—Malton"


def test_parse_expense_csv_real_fixture() -> None:
    rows = parse_expense_csv((FIXTURES / "ontario_mpp_expenses.csv").read_text())
    assert len(rows) > 100
    first = rows[0]
    assert first.incurred_from == date(2023, 11, 1)
    assert first.category == "travel"
    assert first.amount == 586.24
    assert "Queen's Park" in first.purpose
    assert first.location == "Toronto"
    # Every categorized row carries a non-zero amount (credits included).
    assert all(row.amount != 0.0 for row in rows)
    assert {row.category for row in rows} <= {"travel", "accommodation", "meals", "hospitality"}


def test_persist_member_expenses_idempotent(db) -> None:
    from test_ontario_lobbying import _ontario_mpp

    person = _ontario_mpp(db, riding="Mississauga—Malton")
    disclosure = MemberDisclosure(
        ola_slug="deepak-anand",
        csv_url="https://www.ola.org/x/expenses-anand-deepak.csv",
        display_name="Anand, Deepak",
        riding="Mississauga—Malton",
    )
    rows = parse_expense_csv((FIXTURES / "ontario_mpp_expenses.csv").read_text())
    index = _ontario_mpp_index(db)
    fingerprints: set[str] = set()

    created = persist_member_expenses(db, disclosure, rows, index, fingerprints)
    db.commit()
    assert created == len(rows)

    items = db.scalars(select(ExpenseItem)).all()
    assert all(item.scope == "on-mpp" for item in items)
    assert all(item.person_id == person.id for item in items)
    assert items[0].fiscal_year == 2023 and items[0].quarter == 4  # calendar quarters

    # Re-run exactly like the sync does — fingerprints pre-loaded from the DB
    # — and nothing new lands.
    loaded = {fp for (fp,) in db.execute(select(ExpenseItem.fingerprint)).all()}
    again = persist_member_expenses(db, disclosure, rows, index, loaded)
    db.commit()
    assert again == 0
    assert len(db.scalars(select(ExpenseItem)).all()) == created


def test_mpp_expenses_endpoint_and_federal_isolation(db) -> None:
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app
    from app.ingestion.ontario_expenses import _ontario_mpp_index
    from test_ontario_lobbying import _ontario_mpp

    person = _ontario_mpp(db, riding="Mississauga—Malton")
    disclosure = MemberDisclosure(
        ola_slug="deepak-anand",
        csv_url="https://www.ola.org/x/expenses-anand-deepak.csv",
        display_name="Anand, Deepak",
        riding="Mississauga—Malton",
    )
    rows = parse_expense_csv((FIXTURES / "ontario_mpp_expenses.csv").read_text())
    persist_member_expenses(db, disclosure, rows, _ontario_mpp_index(db), set())
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            payload = client.get(f"/v1/politicians/{person.slug}/mpp-expenses").json()
            assert payload["total"] > 0
            assert {t["category"] for t in payload["by_category"]} <= {
                "travel", "accommodation", "meals", "hospitality"
            }
            assert payload["items"]
            assert "ola.org" in payload["source_note"]

            # Ontario rows must NOT leak into the federal explorer...
            federal = client.get("/v1/expenses/search").json()
            assert federal["meta"]["total"] == 0
            # ...but appear under the on-mpp scope.
            provincial = client.get("/v1/expenses/search", params={"scope": "on-mpp"}).json()
            assert provincial["meta"]["total"] == len(rows)
    finally:
        app.dependency_overrides.clear()
