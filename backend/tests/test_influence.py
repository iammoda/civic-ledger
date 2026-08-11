"""Phase 6 tests: influence parsing, entity matching, detectors, review queue."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.data.topics import seed_topics
from app.db.session import get_db
from app.ingestion.influence import (
    normalize_name,
    normalize_person_name,
    parse_contributions_csv,
    parse_lobby_csv,
    sync_contributions,
    sync_lobby_communications,
)
from app.ingestion.sync import SyncContext
from app.main import app
from app.models import (
    Bill,
    BillDeath,
    Contribution,
    EntityTopic,
    IntegrityFlag,
    LobbyCommunication,
    Person,
    Topic,
)
from app.services.detectors import (
    detect_contact_clusters,
    detect_donor_lobbyist_overlap,
    detect_lobbying_before_death,
)
from test_accounts import _seed_auth_user


LOBBY_CSV = """COMM_NUMBER,COMM_DATE,CLIENT_ORG_CORP_NM,REGISTRANT_NM,DPOH_NM,DPOH_TITLE,INSTITUTION,SUBJECT_MATTER
C-100,2026-05-01,Acme Pipelines Inc.,"Smith, Lobby",\"Doe, Jane\",Member of Parliament,House of Commons,"Energy, Environment"
C-101,2026-05-03,Acme Pipelines Inc.,"Smith, Lobby","Doe, Jane",Member of Parliament,House of Commons,"Energy"
C-102,2026-05-05,Big Housing Corp,"Jones, Lobby","Doe, Jane",Member of Parliament,House of Commons,"Housing"
C-103,2026-05-06,Provincial Thing Ltd,"Jones, Lobby","Someone, Provincial",Deputy Minister,Natural Resources Canada,"Mining"
"""

CONTRIB_CSV = """Political entity,Recipient,Political party of recipient,Contributor name,Contributor's city,Contributor's province,Contribution Received date,Monetary amount
Candidate,"Doe, Jane",Liberal Party of Canada,Acme Pipelines Inc.,Calgary,AB,2026-04-15,1500.00
Candidate,"Doe, Jane",Liberal Party of Canada,Regular Person,Ottawa,ON,2026-04-16,50.00
Candidate,"Roe, Bob",Conservative Party of Canada,Someone Else,Toronto,ON,2026-04-17,900.00
"""


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _mp(db, slug="jane-doe", name="Jane Doe") -> Person:
    ctx = SyncContext(db)
    person = Person(slug=slug, full_name=name, chamber_id=ctx.house.id)
    db.add(person)
    db.commit()
    return person


# --- Normalization ---


def test_normalize_name_strips_suffixes() -> None:
    assert normalize_name("Acme Pipelines Inc.") == normalize_name("ACME PIPELINES")
    assert normalize_name("Big Housing Corp") == "big housing"


def test_normalize_person_name_handles_last_first() -> None:
    assert normalize_person_name("Doe, Jane") == "jane doe"
    assert normalize_person_name("Hon. Jane Doe") == "jane doe"
    assert normalize_person_name("Jane Middle Doe") == "jane doe"


# --- Lobby parsing + sync ---


def test_parse_lobby_csv_maps_aliases() -> None:
    rows = parse_lobby_csv(LOBBY_CSV)
    assert len(rows) == 4
    assert rows[0]["source_ref"] == "C-100"
    assert rows[0]["comm_date"] == date(2026, 5, 1)
    assert rows[0]["subjects"] == "Energy, Environment"


def test_sync_lobby_matches_mp_and_filters_institutions(db) -> None:
    mp = _mp(db)
    count = sync_lobby_communications(db, LOBBY_CSV)
    assert count == 3  # Provincial/departmental row filtered out.

    comms = db.scalars(select(LobbyCommunication)).all()
    assert all(c.dpoh_person_id == mp.id for c in comms)
    # Idempotent re-run.
    assert sync_lobby_communications(db, LOBBY_CSV) == 3
    assert len(db.scalars(select(LobbyCommunication)).all()) == 3


def test_parse_lobby_csv_unknown_headers_raise() -> None:
    with pytest.raises(ValueError):
        parse_lobby_csv("A,B,C\n1,2,3\n")


# --- Contributions parsing + sync ---


def test_sync_contributions_dedupes_and_matches(db) -> None:
    mp = _mp(db)
    count = sync_contributions(db, CONTRIB_CSV)
    assert count == 3
    assert sync_contributions(db, CONTRIB_CSV) == 0  # Fingerprint dedupe.

    linked = db.scalars(select(Contribution).where(Contribution.recipient_person_id == mp.id)).all()
    assert len(linked) == 2
    assert {c.amount for c in linked} == {1500.0, 50.0}


# --- Detectors ---


def test_contact_cluster_detector(db) -> None:
    mp = _mp(db)
    # 8 contacts within 10 days -> cluster (min threshold 6).
    for i in range(8):
        db.add(
            LobbyCommunication(
                source_ref=f"C-{i}",
                dpoh_name="Doe, Jane",
                dpoh_person_id=mp.id,
                comm_date=date(2026, 5, 1 + i),
                client_name=f"Client {i % 3}",
            )
        )
    db.commit()

    created = detect_contact_clusters(db)
    assert created == 1
    flag = db.scalar(select(IntegrityFlag))
    assert flag.detector == "lobbying_contact_cluster"
    assert flag.status == "pending_review"  # NEVER auto-published.
    assert "8 lobbying communication reports" in flag.headline_en
    assert len(flag.evidence["communication_ids"]) == 8
    # Re-run must not duplicate.
    assert detect_contact_clusters(db) == 0


def test_donor_lobbyist_overlap_detector(db) -> None:
    mp = _mp(db)
    sync_lobby_communications(db, LOBBY_CSV)
    sync_contributions(db, CONTRIB_CSV)

    created = detect_donor_lobbyist_overlap(db)
    assert created == 1
    flag = db.scalar(select(IntegrityFlag).where(IntegrityFlag.detector == "donor_lobbyist_overlap"))
    assert "Acme Pipelines" in flag.headline_en
    assert flag.status == "pending_review"
    assert flag.evidence["total_amount"] == 1500.0
    # 'Regular Person' ($50) is under threshold and not a lobbying client.
    assert detect_donor_lobbyist_overlap(db) == 0


def test_lobbying_before_death_detector(db) -> None:
    mp = _mp(db)
    seed_topics(db)
    ctx = SyncContext(db)
    session = ctx.session_for_label("45-1")
    bill = Bill(
        session_id=session.id,
        chamber_id=ctx.house.id,
        number="C-99",
        title_en="An Act respecting energy pricing",
        outcome="died_committee",
    )
    db.add(bill)
    db.flush()
    energy = db.scalar(select(Topic).where(Topic.slug == "energy-resources"))
    db.add(EntityTopic(topic_id=energy.id, entity_type="bill", entity_id=bill.id, source="alias"))
    db.add(BillDeath(bill_id=bill.id, mechanism="died_committee", occurred_on=date(2026, 6, 1)))
    # 3 energy-subject communications within the 60-day window.
    for i in range(3):
        db.add(
            LobbyCommunication(
                source_ref=f"D-{i}",
                dpoh_name="Doe, Jane",
                dpoh_person_id=mp.id,
                comm_date=date(2026, 4, 20 + i),
                client_name="Acme Pipelines Inc.",
                subjects="Oil and gas, Energy",
            )
        )
    db.commit()

    created = detect_lobbying_before_death(db)
    assert created == 1
    flag = db.scalar(select(IntegrityFlag).where(IntegrityFlag.detector == "lobbying_before_death"))
    assert "C-99" in flag.headline_en
    assert flag.bill_id == bill.id
    assert flag.status == "pending_review"
    assert "not evidence of causation" in flag.detail_en


# --- Review queue + public visibility ---


def test_flags_hidden_until_published_then_visible(db, client, monkeypatch) -> None:
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.get_settings(), "admin_emails", "jane@example.com")
    _seed_auth_user(db, token="admintok")
    mp = _mp(db)
    db.add(
        IntegrityFlag(
            detector="lobbying_contact_cluster",
            fingerprint="fp1",
            headline_en="Test flag headline.",
            person_id=mp.id,
        )
    )
    db.commit()

    # Public money endpoint: pending flags invisible.
    money = client.get(f"/v1/politicians/{mp.slug}/money").json()
    assert money["flags"] == []

    cookies = {"better-auth.session_token": "admintok.sig"}
    pending = client.get("/v1/admin/flags", cookies=cookies).json()
    assert len(pending) == 1

    reviewed = client.post(
        f"/v1/admin/flags/{pending[0]['id']}",
        json={"action": "publish", "note": "verified against registry"},
        cookies=cookies,
    ).json()
    assert reviewed["status"] == "published"
    assert reviewed["reviewed_by"] == "jane@example.com"

    money = client.get(f"/v1/politicians/{mp.slug}/money").json()
    assert len(money["flags"]) == 1
    assert money["flags"][0]["headline_en"] == "Test flag headline."


def test_admin_requires_admin_email(db, client, monkeypatch) -> None:
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.get_settings(), "admin_emails", "other@example.com")
    _seed_auth_user(db, token="usertok")
    response = client.get("/v1/admin/flags", cookies={"better-auth.session_token": "usertok.sig"})
    assert response.status_code == 403


def test_corrections_flow(db, client, monkeypatch) -> None:
    from app.core import config as config_mod

    submitted = client.post(
        "/v1/corrections",
        json={"page_url": "/politicians/jane-doe", "message": "The attendance number looks wrong, see Hansard."},
    )
    assert submitted.status_code == 201

    monkeypatch.setattr(config_mod.get_settings(), "admin_emails", "jane@example.com")
    _seed_auth_user(db, token="admintok")
    cookies = {"better-auth.session_token": "admintok.sig"}
    open_items = client.get("/v1/admin/corrections", cookies=cookies).json()
    assert len(open_items) == 1

    resolved = client.post(
        f"/v1/admin/corrections/{open_items[0]['id']}",
        json={"note": "Fixed: stats job had stale data."},
        cookies=cookies,
    ).json()
    assert resolved["status"] == "resolved"


def test_money_endpoint_aggregates(db, client) -> None:
    mp = _mp(db)
    sync_lobby_communications(db, LOBBY_CSV)
    sync_contributions(db, CONTRIB_CSV)

    money = client.get(f"/v1/politicians/{mp.slug}/money").json()
    assert money["lobbying_total"] == 3
    assert money["top_clients"][0]["name"] == "Acme Pipelines Inc."
    assert money["donations_total"] == 1550.0
    assert money["top_donors"][0]["name"] == "Acme Pipelines Inc."
    assert "human-reviewed" in money["sources_note"]
