"""Ontario MPP roles: parsing (real fixtures) + sync/end-dating."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.ingestion.ontario_roles import MemberRoles, _role_type, parse_member_roles, sync_member_roles
from app.models import PersonRole

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_premier_roles_real_fixture() -> None:
    parsed = parse_member_roles((FIXTURES / "ontario_member_premier.html").read_text(), "doug-ford")
    assert parsed.riding == "Etobicoke North"
    assert "Premier" in parsed.roles
    assert "Minister of Intergovernmental Affairs" in parsed.roles
    # Deduped (each <li> repeats the title in two spans).
    assert len(parsed.roles) == len(set(parsed.roles))


def test_parse_parliamentary_assistant_real_fixture() -> None:
    parsed = parse_member_roles((FIXTURES / "ontario_member_pa.html").read_text(), "deepak-anand")
    assert parsed.riding == "Mississauga—Malton"
    assert any(role.startswith("Parliamentary Assistant") for role in parsed.roles)


def test_role_type_mapping() -> None:
    assert _role_type("Premier") == "minister"
    assert _role_type("Minister of Health") == "minister"
    assert _role_type("Associate Minister of Small Business") == "minister"
    assert _role_type("Parliamentary Assistant to the Minister of Finance") == "parliamentary_secretary"
    assert _role_type("Speaker of the Legislative Assembly") == "house_officer"
    assert _role_type("Leader, Progressive Conservative Party of Ontario") is None  # party job


def test_sync_member_roles_upserts_and_end_dates(db) -> None:
    from test_ontario_lobbying import _ontario_mpp

    person = _ontario_mpp(db, riding="Etobicoke North")

    created = sync_member_roles(
        db,
        [MemberRoles(ola_slug="doug-ford", riding="Etobicoke North",
                     roles=["Premier", "Minister of Intergovernmental Affairs"])],
    )
    assert created == 2
    roles = db.scalars(select(PersonRole).where(PersonRole.person_id == person.id)).all()
    assert {r.title_en for r in roles} == {"Premier", "Minister of Intergovernmental Affairs"}
    assert all(r.is_current for r in roles)

    # Idempotent re-run creates nothing new.
    assert sync_member_roles(db, [MemberRoles("doug-ford", "Etobicoke North", ["Premier", "Minister of Intergovernmental Affairs"])]) == 0

    # Cabinet shuffle: a dropped role is end-dated, not deleted.
    sync_member_roles(db, [MemberRoles("doug-ford", "Etobicoke North", ["Premier"])])
    roles = {r.title_en: r for r in db.scalars(select(PersonRole).where(PersonRole.person_id == person.id)).all()}
    assert roles["Premier"].is_current is True
    assert roles["Minister of Intergovernmental Affairs"].is_current is False
    assert roles["Minister of Intergovernmental Affairs"].ended_on is not None
