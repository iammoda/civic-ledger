"""Municipal accountability endpoints: attendance, motions, declarations.

Everything here traces to a primary source: each meeting/motion carries the
URL of the official minutes page it was parsed from.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import ConflictDeclaration, Meeting, MeetingAttendance, Motion, Person, Vote

router = APIRouter(prefix="/politicians", tags=["municipal"])


class AttendanceByBody(BaseModel):
    body_name: str
    present: int
    absent: int
    regrets: int
    total_meetings: int


class MotionItem(BaseModel):
    meeting_date: str
    body_name: str
    resolution_number: str | None = None
    item_title: str | None = None
    text_excerpt: str
    role: str  # moved | seconded
    result: str
    source_url: str | None = None
    vote_number: str | None = None
    session_label: str | None = None
    chamber_slug: str | None = None


class DeclarationItem(BaseModel):
    meeting_date: str
    body_name: str
    note: str
    source_url: str | None = None


class MunicipalRecord(BaseModel):
    attendance: list[AttendanceByBody] = []
    attendance_pct: float | None = None  # Across all tracked bodies.
    motions_moved: int = 0
    motions_seconded: int = 0
    recent_motions: list[MotionItem] = []
    declarations: list[DeclarationItem] = []
    meetings_tracked_since: str | None = None


@router.get("/{slug}/municipal", response_model=MunicipalRecord)
def get_municipal_record(slug: str, db: Session = Depends(get_db)) -> MunicipalRecord:
    person = db.scalar(select(Person).where(Person.slug == slug))
    if person is None:
        raise HTTPException(status_code=404, detail="Politician not found")
    if person.chamber_id is None:
        return MunicipalRecord()

    # Attendance grouped by body.
    rows = db.execute(
        select(Meeting.body_name, MeetingAttendance.status, func.count(MeetingAttendance.id))
        .join(Meeting, MeetingAttendance.meeting_id == Meeting.id)
        .where(MeetingAttendance.person_id == person.id)
        .group_by(Meeting.body_name, MeetingAttendance.status)
    ).all()
    by_body: dict[str, dict[str, int]] = {}
    for body, status, count in rows:
        by_body.setdefault(body, {"present": 0, "absent": 0, "regrets": 0})
        if status in by_body[body]:
            by_body[body][status] += count

    totals = dict(
        db.execute(
            select(Meeting.body_name, func.count(Meeting.id))
            .where(Meeting.chamber_id == person.chamber_id, Meeting.minutes_parsed.is_(True))
            .group_by(Meeting.body_name)
        ).all()
    )
    attendance = [
        AttendanceByBody(
            body_name=body,
            present=counts["present"],
            absent=counts["absent"],
            regrets=counts["regrets"],
            total_meetings=totals.get(body, sum(counts.values())),
        )
        for body, counts in sorted(by_body.items())
    ]
    present_total = sum(a.present for a in attendance)
    recorded_total = sum(a.present + a.absent + a.regrets for a in attendance)
    attendance_pct = round(100.0 * present_total / recorded_total, 1) if recorded_total else None

    first_meeting = db.scalar(
        select(func.min(Meeting.meeting_date)).where(
            Meeting.chamber_id == person.chamber_id, Meeting.minutes_parsed.is_(True)
        )
    )

    moved = db.scalar(
        select(func.count(Motion.id)).where(Motion.mover_person_id == person.id)
    ) or 0
    seconded = db.scalar(
        select(func.count(Motion.id)).where(Motion.seconder_person_id == person.id)
    ) or 0

    recent = db.scalars(
        select(Motion)
        .join(Meeting, Motion.meeting_id == Meeting.id)
        .where((Motion.mover_person_id == person.id) | (Motion.seconder_person_id == person.id))
        .options(
            selectinload(Motion.meeting),
            selectinload(Motion.vote).selectinload(Vote.session),
            selectinload(Motion.vote).selectinload(Vote.chamber),
        )
        .order_by(Meeting.meeting_date.desc(), Motion.sequence.desc())
        .limit(15)
    ).all()
    recent_motions = []
    for motion in recent:
        vote = motion.vote
        recent_motions.append(
            MotionItem(
                meeting_date=motion.meeting.meeting_date.isoformat(),
                body_name=motion.meeting.body_name,
                resolution_number=motion.resolution_number,
                item_title=motion.item_title,
                text_excerpt=(motion.text_en or "")[:280],
                role="moved" if motion.mover_person_id == person.id else "seconded",
                result=motion.result,
                source_url=motion.source_url,
                vote_number=vote.number if vote else None,
                session_label=vote.session.label if vote else None,
                chamber_slug=vote.chamber.slug if vote else None,
            )
        )

    declarations = [
        DeclarationItem(
            meeting_date=decl.meeting.meeting_date.isoformat(),
            body_name=decl.meeting.body_name,
            note=decl.note,
            source_url=decl.meeting.minutes_url,
        )
        for decl in db.scalars(
            select(ConflictDeclaration)
            .join(Meeting, ConflictDeclaration.meeting_id == Meeting.id)
            .where(ConflictDeclaration.person_id == person.id)
            .options(selectinload(ConflictDeclaration.meeting))
            .order_by(Meeting.meeting_date.desc())
            .limit(25)
        ).all()
    ]

    return MunicipalRecord(
        attendance=attendance,
        attendance_pct=attendance_pct,
        motions_moved=moved,
        motions_seconded=seconded,
        recent_motions=recent_motions,
        declarations=declarations,
        meetings_tracked_since=first_meeting.isoformat() if first_meeting else None,
    )
