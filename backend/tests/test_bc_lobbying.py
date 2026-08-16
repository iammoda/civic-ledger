"""BC lobbying: ORL open-data parsing + sync (synthetic mini exports)."""
from __future__ import annotations

import io
import zipfile
from datetime import date

from sqlalchemy import select

from app.ingestion.bc_lobbying import (
    parse_lar_zip,
    sync_bc_communications,
    sync_bc_registrations,
)
from app.models import Chamber, Jurisdiction, LobbyCommunication, LobbyRegistration, Person


def _zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buffer.getvalue()


def build_lar_zip() -> bytes:
    return _zip(
        {
            "LAR_Primary_Export.csv": (
                "LAR_ID,CLIENT_ORG_NUM,CLIENT_ORG_NAME,FILER_NUM,FILER_LAST_NAME,FILER_FIRST_NAME,"
                "MEETING_DATE,ARRANGE_MEETING,REG_TYPE,SUBMISSION_DATE,POSTED_DATE,"
                "PREVIOUS_VERSION_LAR_ID,LOBBYIST_ID,IH_LOBBYIST_LAST_NAME,IH_LOBBYIST_FIRST_NAME,COALITION_MEMBER_NAME\n"
                "LAR-1,10,Acme Pipelines Inc.,55,Smith,Jane,2026-05-01,N,Cons,2026-05-02,2026-05-02,null,null,null,null,null\n"
                # LAR-2 supersedes LAR-1a (amended report)
                "LAR-1a,10,Acme Pipelines Inc.,55,Smith,Jane,2026-05-01,N,Cons,2026-05-02,2026-05-02,null,null,null,null,null\n"
                "LAR-2,10,Acme Pipelines Inc.,55,Smith,Jane,2026-05-01,N,Cons,2026-05-03,2026-05-03,LAR-1a,null,null,null,null\n"
                # too old — filtered by since_year
                "LAR-3,11,Old Org,56,Doe,John,2001-01-01,N,Org,2001-01-02,2001-01-02,null,null,Doe,John,null\n"
            ),
            "LAR_SPOH_Export.csv": (
                "LAR_ID,SPOH_LAST_NAME,SPOH_FIRST_NAME,SPOH_TITLE,BRANCH,BC_PUBLIC_AGENCY\n"
                "LAR-1,Carr,Wendy,MLA,,Legislative Assembly\n"
                "LAR-1,Deep,Bureaucrat,Deputy Minister,Energy,Energy\n"
                "LAR-2,Carr,Wendy,MLA,,Legislative Assembly\n"
            ),
            "LAR_SubjectMatterDetails_Export.csv": (
                "LAR_ID,INTENDED_OUTCOME_IDS,TOPIC_OF_LOBBYING,SUBJECT_MATTER_IDS\n"
                'LAR-1,BC-01,Pipeline approvals,"SM-10, SM-12"\n'
            ),
            "Subject_Matters_Export.csv": (
                "SUBJECT_MATTER_ID,SUBJECT_MATTER\nSM-10,Energy\nSM-12,Environment\n"
            ),
        }
    )


def build_registrations_zip() -> bytes:
    return _zip(
        {
            "Registration_Primary_Export.csv": (
                "REG_ID,REG_TYPE,REG_NUM,USER_PROFILE_ID,LOBB_ACT_CODE,FIRM_NAME,FIRM_ADDRESS,FILER_NUM,"
                "FILER_LAST_NAME,FILER_FIRST_NAME,FILER_MIDDLE_NAME,FILER_POSITION_TITLE,FILER_ADDRESS,"
                "CLIENT_ORG_PROFILE_ID,CLIENT_ORG_NUM,CLIENT_ORG_NAME,CLIENT_ORG_ADDRESS,DATE_OF_WRIT,"
                "CLIENT_LOBBY_MLA_IND,CLIENT_CONTRIBUTIONS_POLITICAL,CLIENT_CONTRIBUTIONS_SPONSORSHIP,"
                "CLIENT_CONTRIBUTIONS_RECALL,CLIENT_ORG_BUS_DESC,CLIENT_ORG_WEB_ADDRESS,REG_START_DATE,"
                "REG_PROJECTED_END_DATE,REG_END_DATE,REG_POSTED_DATE,AFFILIATES_IND,COALITION_IND,"
                "CONTRIBUTORS_IND,DIRECT_INT_IND,GOVT_FUND_IND,PREVIOUS_VERSION_REG_ID,ARRANGE_MEETING\n"
                # active consultant registration
                "R-1,Cons,100-1-1,UP-1,V5,Firm LLP,null,55,Smith,Jane,null,Principal,null,CP-1,10,"
                "Acme Pipelines Inc.,null,null,null,null,null,null,Pipelines,null,2026-01-01,2026-12-31,"
                "null,2026-01-02,N,N,N,N,N,null,Y\n"
                # ended in-house registration (skipped)
                "R-2,Org,200-2-2,UP-2,V5,null,null,56,Doe,John,null,VP,null,CP-2,11,Beta Org,null,null,"
                "null,null,null,null,Widgets,null,2024-01-01,2025-01-01,2025-06-01,2024-01-02,N,N,N,N,N,null,N\n"
            ),
        }
    )


def _bc_mla(db, name: str = "Wendy Carr") -> Person:
    jurisdiction = Jurisdiction(code="bc", name_en="British Columbia", level="provincial")
    db.add(jurisdiction)
    db.flush()
    chamber = Chamber(jurisdiction_id=jurisdiction.id, slug="bc-assembly", name_en="Legislative Assembly of BC")
    db.add(chamber)
    db.flush()
    person = Person(slug="bc-wendy-carr", full_name=name, chamber_id=chamber.id)
    db.add(person)
    db.commit()
    return person


def test_parse_lar_zip_supersedes_and_filters() -> None:
    rows = parse_lar_zip(build_lar_zip(), since_year=2019)
    refs = {(row["source_ref"], row["dpoh_name"]) for row in rows}
    assert ("LAR-1", "Wendy Carr") in refs
    assert ("LAR-2", "Wendy Carr") in refs
    assert not any(ref == "LAR-1a" for ref, _ in refs)  # superseded
    assert not any(ref == "LAR-3" for ref, _ in refs)  # too old
    first = next(row for row in rows if row["source_ref"] == "LAR-1" and row["dpoh_name"] == "Wendy Carr")
    assert first["comm_date"] == date(2026, 5, 1)
    assert "Energy" in first["subjects"] and "Pipeline approvals" in first["subjects"]
    assert first["dpoh_title"] == "MLA"


def test_sync_bc_communications_matches_mlas_and_dedupes(db) -> None:
    person = _bc_mla(db)
    count = sync_bc_communications(db, build_lar_zip())
    assert count == 3  # LAR-1 x2 SPOHs + LAR-2 x1

    comms = db.scalars(select(LobbyCommunication)).all()
    assert all(c.jurisdiction_code == "bc" for c in comms)
    mla_rows = [c for c in comms if c.dpoh_name == "Wendy Carr"]
    assert all(c.dpoh_person_id == person.id for c in mla_rows)
    bureaucrat = next(c for c in comms if c.dpoh_name == "Bureaucrat Deep")
    assert bureaucrat.dpoh_person_id is None  # unelected: stored, unmatched

    # Idempotent.
    assert sync_bc_communications(db, build_lar_zip()) == 0


def test_sync_bc_registrations_active_only_and_end_dating(db) -> None:
    assert sync_bc_registrations(db, build_registrations_zip()) == 1
    registration = db.scalar(select(LobbyRegistration))
    assert registration.jurisdiction_code == "bc"
    assert registration.registration_number == "100-1-1"
    assert registration.client_name == "Acme Pipelines Inc."
    assert registration.lobbyist_type == "consultant"
    assert registration.status == "active"

    # Unchanged re-run is a no-op.
    assert sync_bc_registrations(db, build_registrations_zip()) == 0

    # If it disappears from the active export, it gets ended — not orphaned.
    empty = _zip({"Registration_Primary_Export.csv":
                  "REG_ID,REG_TYPE,REG_NUM,USER_PROFILE_ID,LOBB_ACT_CODE,FIRM_NAME,FIRM_ADDRESS,FILER_NUM,"
                  "FILER_LAST_NAME,FILER_FIRST_NAME,FILER_MIDDLE_NAME,FILER_POSITION_TITLE,FILER_ADDRESS,"
                  "CLIENT_ORG_PROFILE_ID,CLIENT_ORG_NUM,CLIENT_ORG_NAME,CLIENT_ORG_ADDRESS,DATE_OF_WRIT,"
                  "CLIENT_LOBBY_MLA_IND,CLIENT_CONTRIBUTIONS_POLITICAL,CLIENT_CONTRIBUTIONS_SPONSORSHIP,"
                  "CLIENT_CONTRIBUTIONS_RECALL,CLIENT_ORG_BUS_DESC,CLIENT_ORG_WEB_ADDRESS,REG_START_DATE,"
                  "REG_PROJECTED_END_DATE,REG_END_DATE,REG_POSTED_DATE,AFFILIATES_IND,COALITION_IND,"
                  "CONTRIBUTORS_IND,DIRECT_INT_IND,GOVT_FUND_IND,PREVIOUS_VERSION_REG_ID,ARRANGE_MEETING\n"})
    sync_bc_registrations(db, empty)
    assert db.scalar(select(LobbyRegistration.status)) == "ended"
