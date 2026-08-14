"""Represent people sync: idempotent upserts, slugs, retirement, matching."""
from __future__ import annotations

from app.ingestion.represent_people import (
    _ensure_chamber,
    _ensure_jurisdiction,
    person_slug_for,
    person_source_id,
    set_slug_from_url,
    upsert_representative,
)
from app.models import Chamber, Jurisdiction, Person, PersonMembership
from app.services.represent import _match_represent_person


MPP_REP = {
    "name": "Natalia Kusendova-Bashta",
    "first_name": "Natalia",
    "last_name": "Kusendova-Bashta",
    "district_name": "Mississauga Centre",
    "elected_office": "MPP",
    "party_name": "Progressive Conservative Party of Ontario",
    "email": "natalia.kusendova@pc.ola.org",
    "photo_url": "https://example.com/photo.jpg",
    "url": "https://www.ola.org/en/members/all/natalia-kusendova-bashta",
    "offices": [{"tel": "1 416 325-1234", "type": "legislature", "postal": "Queen's Park"}],
    "related": {"representative_set_url": "/representative-sets/ontario-legislature/"},
}

COUNCILLOR_REP = {
    "name": "John Kovac",
    "district_name": "Ward 4",
    "elected_office": "Councillor",
    "party_name": "",
    "email": "john.kovac@mississauga.ca",
    "url": "https://example.com/kovac",
    "offices": [],
    "related": {"representative_set_url": "/representative-sets/mississauga-city-council/"},
}


def _sync_one(db, rep, set_slug, set_name):
    jur = _ensure_jurisdiction(db, set_slug, set_name)
    chamber = _ensure_chamber(db, jur, set_name)
    return upsert_representative(
        db, rep, set_slug=set_slug, jurisdiction=jur, chamber=chamber, party_cache={}
    )


def test_slug_derivation():
    assert person_slug_for("ontario-legislature", "David Smith") == "on-david-smith"
    assert (
        person_slug_for("mississauga-city-council", "Alvin Tedjo")
        == "mississauga-city-council-alvin-tedjo"
    )
    assert person_source_id("ontario-legislature", "France Gélinas") == (
        "ontario-legislature/france-gelinas"
    )
    assert set_slug_from_url("/representative-sets/ontario-legislature/") == "ontario-legislature"


def test_upsert_is_idempotent(db):
    first = _sync_one(db, MPP_REP, "ontario-legislature", "Legislative Assembly of Ontario")
    second = _sync_one(db, MPP_REP, "ontario-legislature", "Legislative Assembly of Ontario")
    db.commit()

    assert first.id == second.id
    assert db.query(Person).count() == 1
    assert db.query(PersonMembership).count() == 1
    assert db.query(Jurisdiction).filter_by(code="ca-on").one().level == "provincial"
    assert first.slug == "on-natalia-kusendova-bashta"
    assert first.offices_json[0]["type"] == "legislature"

    membership = db.query(PersonMembership).one()
    assert membership.riding_name == "Mississauga Centre"
    assert membership.role_title == "MPP"
    assert membership.province_code == "ON"
    assert membership.party.name_en == "Progressive Conservative Party of Ontario"


def test_provincial_chamber_slug_is_prefixed(db):
    _sync_one(db, MPP_REP, "ontario-legislature", "Legislative Assembly of Ontario")
    chamber = db.query(Chamber).one()
    assert chamber.slug == "on-assembly"


def test_municipal_jurisdiction_uses_set_slug(db):
    person = _sync_one(db, COUNCILLOR_REP, "mississauga-city-council", "Mississauga City Council")
    db.commit()
    jur = db.query(Jurisdiction).filter_by(code="mississauga-city-council").one()
    assert jur.level == "municipal"
    assert person.slug == "mississauga-city-council-john-kovac"
    # No party for municipal reps without one.
    assert db.query(PersonMembership).one().party_id is None


def test_mp_and_councillor_same_name_do_not_collide(db):
    # A federal MP named John Kovac (openparliament source).
    db.add(Person(slug="john-kovac", full_name="John Kovac", source_system="openparliament"))
    db.commit()
    person = _sync_one(db, COUNCILLOR_REP, "mississauga-city-council", "Mississauga City Council")
    db.commit()
    assert person.slug != "john-kovac"
    assert db.query(Person).count() == 2


def test_match_represent_person_uses_natural_key(db):
    _sync_one(db, MPP_REP, "ontario-legislature", "Legislative Assembly of Ontario")
    db.commit()
    assert _match_represent_person(db, MPP_REP) == "on-natalia-kusendova-bashta"
    assert _match_represent_person(db, COUNCILLOR_REP) is None


def test_represent_sync_adopts_ola_vote_roll_stub(db):
    """An MPP first seen in an ola.org division gets adopted, not duplicated,
    once Represent's roster catches up."""
    from app.ingestion.ontario import OntarioSyncContext

    ctx = OntarioSyncContext(db)
    stub = ctx.ensure_person("Hon. Natalia Kusendova-Bashta")
    db.commit()
    assert stub.source_system == "ola"
    assert stub.slug == "on-natalia-kusendova-bashta"

    person = _sync_one(db, MPP_REP, "ontario-legislature", "Legislative Assembly of Ontario")
    db.commit()
    assert person.id == stub.id
    assert person.source_system == "represent"
    assert person.email == "natalia.kusendova@pc.ola.org"
    assert db.query(Person).count() == 1
    assert db.query(PersonMembership).count() == 1
