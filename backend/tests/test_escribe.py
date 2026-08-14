"""eScribe minutes ingestion: parsers + idempotent persistence + matching."""
from __future__ import annotations

from datetime import date

import pytest

from app.ingestion.escribe import (
    EscribeSyncContext,
    EscribeTenant,
    normalize_minutes_name,
    parse_minutes,
)
from app.models import (
    Ballot,
    Chamber,
    ConflictDeclaration,
    Jurisdiction,
    Meeting,
    MeetingAttendance,
    Motion,
    Person,
    Vote,
)


MINUTES_HTML = """
<div class='AgendaHeaderAttendance'><div class='AgendaHeaderAttendanceTable'><div>
  <div class='Label'>Members</div>
  <div class='Value'><ul>
    <li>Mayor Carolyn Parrish</li>
    <li>Deputy Mayor and Councillor John Kovac,&nbsp;Ward 4</li>
    <li>Councillor Brad Butt,&nbsp;Ward 11</li>
  </ul></div>
</div><div>
  <div class='Label'>Members Absent</div>
  <div class='Value'><ul><li>Councillor Dipika Damerla,&nbsp;Ward 7</li></ul></div>
</div><div>
  <div class='Label'>Staff Present</div>
  <div class='Value'><ul><li>Some Bureaucrat, City Manager</li></ul></div>
</div></div></div>

<div class='AgendaItemContainer'>
  <h2>4. DECLARATION OF CONFLICT OF INTEREST</h2>
  <div class='AgendaItemContentRow indent'><div class='AgendaItemMinutes RichText'>
    <p>Councillor Brad Butt declared a conflict on item 10.2 (family member employed by the vendor).</p>
  </div></div>
</div>

<div class='AgendaItemContainer'>
  <h2>9. CONSENT AGENDA</h2>
  <ul class='AgendaItemMotions'><li class='AgendaItemMotion'>
    <div class='Number'><span class='Label'>RESOLUTION</span><span class='Value'><u>0100-2026</u></span></div>
    <div class='MovedBy'><span class='Label'>Moved By</span><span class='Value'>Councillor B. Butt</span></div>
    <div class='SecondedBy'><span class='Label'>Seconded By</span><span class='Value'>Councillor J. Kovac</span></div>
    <div class='MotionText RichText'><p>The following items were approved on the consent agenda.</p></div>
    <table class='MotionVoters'><tbody>
      <tr><td class='VoterVote'>YES (2)</td><td class='VotesUsers'>Councillor B. Butt,  and Councillor J. Kovac</td></tr>
      <tr><td class='VoterVote'>ABSENT (1)</td><td class='VotesUsers'>Mayor C. Parrish</td></tr>
    </tbody></table>
    <div class='MotionResult'>Carried (2 to 0)</div>
  </li></ul>
</div>
"""

NARRATIVE_HTML = """
<div class='AgendaHeaderAttendance'><div><div>
  <div class='Label'>Members Present:</div>
  <div class='Value'><ul><li>Mayor Patrick Brown</li></ul></div>
</div></div></div>
<div class='AgendaItemContainer'>
  <h2>3. APPROVAL OF MINUTES</h2>
  <div class='AgendaItemMinutes RichText'>
    <p>MOVED by Councillor Steele, seconded by Councillor Gillis</p>
    <p><strong>THAT the minutes of May 26, 2026 be approved as circulated.</strong></p>
    <p><strong>MOTION PUT AND PASSED.</strong></p>
  </div>
</div>
"""


def test_normalize_minutes_name():
    assert normalize_minutes_name("Deputy Mayor and Councillor John Kovac, Ward 4") == "john kovac"
    assert normalize_minutes_name("Mayor Carolyn Parrish") == "carolyn parrish"
    assert normalize_minutes_name("Regional Councillor R. Santos") == "r. santos"


def test_parse_minutes_structure():
    parsed = parse_minutes(MINUTES_HTML)
    statuses = {a.name: a.status for a in parsed.attendance}
    assert statuses["Mayor Carolyn Parrish"] == "present"
    assert statuses["Councillor Dipika Damerla, Ward 7"] == "absent"
    assert not any("Bureaucrat" in a.name for a in parsed.attendance)  # Staff excluded.

    assert len(parsed.motions) == 1
    motion = parsed.motions[0]
    assert motion.resolution_number == "0100-2026"
    assert motion.mover == "Councillor B. Butt"
    assert motion.seconder == "Councillor J. Kovac"
    assert motion.result == "carried"
    assert motion.item_title == "9. CONSENT AGENDA"
    assert motion.votes["yea"] == ["Councillor B. Butt", "Councillor J. Kovac"]
    assert motion.votes["absent"] == ["Mayor C. Parrish"]

    assert len(parsed.declarations) == 1
    assert "Brad Butt" in parsed.declarations[0]


def test_parse_narrative_motions_fallback():
    parsed = parse_minutes(NARRATIVE_HTML)
    assert len(parsed.motions) == 1
    motion = parsed.motions[0]
    assert motion.mover == "Councillor Steele"
    assert motion.seconder == "Councillor Gillis"
    assert motion.result == "carried"
    assert "approved as circulated" in motion.text


@pytest.fixture()
def mississauga(db):
    jur = Jurisdiction(code="mississauga-city-council", name_en="Mississauga City Council", level="municipal")
    db.add(jur)
    db.flush()
    chamber = Chamber(jurisdiction_id=jur.id, slug="council", name_en="Mississauga City Council")
    db.add(chamber)
    db.flush()
    for name in ("Carolyn Parrish", "John Kovac", "Brad Butt", "Dipika Damerla"):
        person = Person(
            slug=f"mississauga-{name.lower().replace(' ', '-')}",
            full_name=name,
            chamber_id=chamber.id,
            source_system="represent",
        )
        db.add(person)
    db.commit()
    return EscribeTenant(
        tenant="mississauga",
        jurisdiction_code="mississauga-city-council",
        bodies=("Council",),
        term_start=date(2022, 11, 15),
    )


def test_persist_minutes_idempotent(db, mississauga):
    from app.ingestion.escribe import (
        _persist_attendance,
        _persist_declarations,
        _persist_motions,
        _upsert_meeting,
    )

    ctx = EscribeSyncContext(db, mississauga)
    raw = {"ID": "guid-1", "MeetingName": "Council", "StartDate": "2026/05/13 09:30:00"}
    parsed = parse_minutes(MINUTES_HTML)

    for _ in range(2):
        meeting = _upsert_meeting(ctx, raw, "https://example.com/minutes")
        _persist_attendance(ctx, meeting, parsed.attendance)
        _persist_motions(ctx, meeting, parsed.motions)
        _persist_declarations(ctx, meeting, parsed.declarations)
        db.commit()

    assert db.query(Meeting).count() == 1
    assert db.query(MeetingAttendance).count() == 4
    assert db.query(Motion).count() == 1
    assert db.query(Vote).count() == 1
    assert db.query(Ballot).count() == 3
    assert db.query(ConflictDeclaration).count() == 1

    # Initial-form matching: "Councillor B. Butt" -> Brad Butt.
    motion = db.query(Motion).one()
    assert motion.mover.full_name == "Brad Butt"
    assert motion.seconder.full_name == "John Kovac"
    assert motion.vote_id is not None

    ballots = {b.person.full_name: b.ballot for b in db.query(Ballot).all()}
    assert ballots == {"Brad Butt": "yea", "John Kovac": "yea", "Carolyn Parrish": "absent"}

    declaration = db.query(ConflictDeclaration).one()
    assert declaration.person.full_name == "Brad Butt"

    attendance = {a.person.full_name: a.status for a in db.query(MeetingAttendance).all()}
    assert attendance["Dipika Damerla"] == "absent"
    assert attendance["Carolyn Parrish"] == "present"

    # Provenance: everything points at the official minutes.
    assert db.query(Meeting).one().minutes_url == "https://example.com/minutes"
    assert motion.source_url == "https://example.com/minutes"
    assert db.query(Vote).one().source_url == "https://example.com/minutes"
