"""Ontario lobbyist registry: parsers (real fixtures) + sync plumbing."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.ingestion.ontario_lobbying import (
    GridRow,
    RegistrationDetail,
    mpp_riding,
    parse_grid_rows,
    parse_next_page_target,
    parse_registration_detail,
    parse_total_items,
    upsert_registration,
)
from app.models import LobbyRegistration, LobbyRegistrationMpp

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text()


# --- Grid parsing -----------------------------------------------------------


def test_parse_grid_rows_real_fixture() -> None:
    html = _read("ontario_lobbying_grid.html")
    rows = parse_grid_rows(html)
    assert len(rows) == 10
    first = rows[0]
    assert first.lobbyist_name == "Kevin Townsend"
    assert first.last_amendment_date == date(2026, 8, 14)
    assert first.client_name == "Anatolia Investments Corp"
    assert first.firm_name == "Sussex Strategy Group"
    assert first.lobbyist_type == "consultant"
    assert first.registration_number.startswith("CL10523-")
    assert first.status == "active"


def test_parse_grid_pager_and_total() -> None:
    html = _read("ontario_lobbying_grid.html")
    assert parse_total_items(html) == 4095
    target = parse_next_page_target(html)
    assert target and "GridRegistrationList" in target


# --- Detail parsing ---------------------------------------------------------


def test_parse_consultant_registration_detail() -> None:
    detail = parse_registration_detail(_read("ontario_lobbying_consultant.html"))
    assert detail.registration_number == "CL10523-20260811037393"
    assert detail.lobbyist_name == "Kevin Townsend"
    assert detail.firm_name == "Sussex Strategy Group"
    assert detail.initial_filing_date == date(2026, 8, 11)
    assert detail.subject_matters == "Economic development and trade"
    assert "MTO site plan changes" in (detail.goals or "")
    assert "Office of the Minister of Transportation" in detail.target_ministries
    assert "Ministry of Transportation" in detail.target_ministries
    assert detail.target_mpp_offices == ["Office of the Member for Niagara West"]


def test_parse_inhouse_registration_detail() -> None:
    detail = parse_registration_detail(_read("ontario_lobbying_inhouse.html"))
    assert detail.registration_number.startswith("OL")
    assert detail.lobbyist_name
    # In-house filings list many subjects, semicolon-normalized.
    assert ";" in (detail.subject_matters or "")
    assert "Hospitals" in detail.subject_matters
    assert any("Minister" in m for m in detail.target_ministries)


def test_mpp_riding_extraction() -> None:
    assert mpp_riding("Office of the Member for Niagara West") == "Niagara West"
    assert mpp_riding("Office of the Minister of Health") is None


# --- Upsert -----------------------------------------------------------------


def _row(number: str = "CL1-20260101000001") -> GridRow:
    return GridRow(
        lobbyist_name="Jane Lobbyist",
        last_amendment_date=date(2026, 1, 2),
        client_name="Acme Corp",
        firm_name="Firm LLP",
        lobbyist_type="consultant",
        registration_number=number,
        status="active",
    )


def _detail(number: str = "CL1-20260101000001") -> RegistrationDetail:
    return RegistrationDetail(
        registration_number=number,
        lobbyist_name="Jane Lobbyist",
        firm_name="Firm LLP",
        client_name="Acme Corp",
        subject_matters="Housing",
        goals="Change zoning rules",
        target_ministries=["Ministry of Municipal Affairs and Housing"],
        target_mpp_offices=["Office of the Member for Testville", "Office of the Member for Nowhere"],
        techniques="Meetings",
    )


def _ontario_mpp(db, riding: str = "Testville"):
    from app.models import Chamber, Jurisdiction, Person, PersonMembership

    jurisdiction = Jurisdiction(code="on", name_en="Ontario", level="provincial")
    db.add(jurisdiction)
    db.flush()
    chamber = Chamber(jurisdiction_id=jurisdiction.id, slug="on-assembly", name_en="Legislative Assembly of Ontario")
    db.add(chamber)
    db.flush()
    person = Person(slug="on-test-mpp", full_name="Test MPP", chamber_id=chamber.id)
    db.add(person)
    db.flush()
    db.add(
        PersonMembership(
            person_id=person.id, chamber_id=chamber.id, riding_name=riding,
            started_on=date(2025, 1, 1), is_current=True,
        )
    )
    db.commit()
    return person


def test_upsert_registration_links_mpps_and_is_idempotent(db) -> None:
    person = _ontario_mpp(db)
    from app.ingestion.ontario_lobbying import _ontario_mpp_index

    index = _ontario_mpp_index(db)
    assert index == {"testville": person.id}

    upsert_registration(db, _row(), _detail(), index)
    db.commit()
    registration = db.scalar(select(LobbyRegistration))
    assert registration.client_name == "Acme Corp"
    assert registration.subject_matters == "Housing"
    links = db.scalars(select(LobbyRegistrationMpp)).all()
    # "Nowhere" has no sitting MPP -> only the resolvable riding links.
    assert [(link.person_id, link.riding_as_filed) for link in links] == [(person.id, "Testville")]

    # Amendment: same registration number, updated targets — no duplicates.
    updated = _detail()
    updated.target_mpp_offices = []
    updated.subject_matters = "Housing; Taxation"
    upsert_registration(db, _row(), updated, index)
    db.commit()
    assert db.scalar(select(LobbyRegistration.subject_matters)) == "Housing; Taxation"
    assert db.scalars(select(LobbyRegistrationMpp)).all() == []


# --- API --------------------------------------------------------------------


def test_ontario_lobbying_endpoints(db) -> None:
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app

    person = _ontario_mpp(db)
    from app.ingestion.ontario_lobbying import _ontario_mpp_index

    upsert_registration(db, _row(), _detail(), _ontario_mpp_index(db))
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            # Explorer: token search + subject/ministry filters.
            payload = client.get("/v1/lobbying/ontario", params={"q": "acme"}).json()
            assert payload["total"] == 1
            item = payload["items"][0]
            assert item["client_name"] == "Acme Corp"
            assert item["target_ministries"] == ["Ministry of Municipal Affairs and Housing"]
            assert "REGISTRATIONS" in payload["registry_note"]

            assert client.get("/v1/lobbying/ontario", params={"ministry": "municipal affairs"}).json()["total"] == 1
            assert client.get("/v1/lobbying/ontario", params={"subject": "fisheries"}).json()["total"] == 0

            # Per-MPP: registrations naming their office.
            mine = client.get(f"/v1/politicians/{person.slug}/lobbying-registrations").json()
            assert mine["total"] == 1
            assert mine["items"][0]["registration_number"].startswith("CL1-")
            assert client.get("/v1/politicians/nobody/lobbying-registrations").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_ministry_targets_resolve_to_sitting_minister(db) -> None:
    from datetime import date as date_type

    from app.ingestion.ontario_lobbying import (
        _ontario_minister_index,
        backfill_ministry_links,
        resolve_ministry_target,
    )
    from app.models import PersonRole

    minister = _ontario_mpp(db, riding="Etobicoke North")
    db.add(
        PersonRole(
            person_id=minister.id, role_type="minister",
            title_en="Minister of Transportation", is_current=True,
            started_on=date_type(2025, 1, 1),
        )
    )
    db.commit()

    index = _ontario_minister_index(db)
    assert resolve_ministry_target("Office of the Minister of Transportation", index) == minister.id
    assert resolve_ministry_target("Ministry of Transportation", index) == minister.id
    assert resolve_ministry_target("Ministry of Health", index) is None

    # Upsert links ministry targets with target_kind=ministry.
    detail = _detail()
    detail.target_ministries = ["Ministry of Transportation"]
    detail.target_mpp_offices = []
    upsert_registration(db, _row(), detail, {}, index)
    db.commit()
    link = db.scalar(select(LobbyRegistrationMpp))
    assert link.person_id == minister.id and link.target_kind == "ministry"

    # Backfill is idempotent (person already linked).
    assert backfill_ministry_links(db) == 0


def test_backfill_links_existing_registrations(db) -> None:
    from datetime import date as date_type

    from app.ingestion.ontario_lobbying import backfill_ministry_links
    from app.models import PersonRole

    minister = _ontario_mpp(db, riding="Etobicoke North")
    # Registration crawled BEFORE any roles existed: no links.
    detail = _detail()
    detail.target_ministries = ["Office of the Minister of Transportation"]
    detail.target_mpp_offices = []
    upsert_registration(db, _row(), detail, {}, {})
    db.commit()
    assert db.scalars(select(LobbyRegistrationMpp)).all() == []

    db.add(
        PersonRole(
            person_id=minister.id, role_type="minister",
            title_en="Minister of Transportation", is_current=True,
            started_on=date_type(2025, 1, 1),
        )
    )
    db.commit()
    assert backfill_ministry_links(db) == 1
    link = db.scalar(select(LobbyRegistrationMpp))
    assert link.person_id == minister.id and link.target_kind == "ministry"


def test_two_phase_stub_then_detail(db) -> None:
    from app.ingestion.ontario_lobbying import apply_detail, upsert_stub

    # Phase 1: the stub is listed immediately with grid data only.
    registration = upsert_stub(db, _row())
    db.commit()
    assert registration.detail_synced is False
    assert registration.client_name == "Acme Corp"
    assert registration.goals is None  # details not fetched yet

    # Phase 2: detail fills the filing and flips the flag.
    apply_detail(db, registration, _detail(), {}, {})
    db.commit()
    assert registration.detail_synced is True
    assert registration.goals == "Change zoning rules"
    assert registration.subject_matters == "Housing"

    # An amendment (new date) marks it for re-fetch without losing data.
    amended = _row()
    amended.last_amendment_date = amended.last_amendment_date.replace(day=5)
    upsert_stub(db, amended)
    db.commit()
    assert registration.detail_synced is False
    assert registration.goals == "Change zoning rules"  # old detail retained meanwhile

    # Re-walking the SAME amendment date doesn't clear the synced flag.
    apply_detail(db, registration, _detail(), {}, {})
    upsert_stub(db, amended)
    db.commit()
    assert registration.detail_synced is True
