from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import (
    Bill,
    Chamber,
    CommitteeMembership,
    LegislatureSession,
    Party,
    Person,
    PersonMembership,
    PersonStats,
)
from app.schemas.common import MembershipSummary, PageMeta
from app.schemas.politicians import (
    CommitteeMembershipSummary,
    PoliticianDetail,
    PoliticianListItem,
    PoliticianVoteStats,
)


router = APIRouter(prefix="/politicians", tags=["politicians"])


def _current_membership(person: Person) -> PersonMembership | None:
    for membership in person.memberships:
        if membership.is_current:
            return membership
    return person.memberships[0] if person.memberships else None


@router.get("")
def list_politicians(
    party: str | None = None,
    province: str | None = None,
    chamber: str | None = None,
    limit: int = Query(default=25, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    query = select(Person)
    if chamber:
        query = query.join(Chamber, Person.chamber_id == Chamber.id).where(Chamber.slug == chamber)
    if party:
        query = query.where(
            Person.memberships.any(
                and_(
                    PersonMembership.is_current.is_(True),
                    PersonMembership.party.has(Party.slug == party),
                )
            )
        )
    if province:
        query = query.where(
            Person.memberships.any(
                and_(
                    PersonMembership.is_current.is_(True),
                    PersonMembership.province_code == province,
                )
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    people = db.scalars(
        query.options(
            selectinload(Person.memberships).selectinload(PersonMembership.party),
            selectinload(Person.chamber),
        )
        .order_by(Person.full_name)
        .offset(offset)
        .limit(limit)
    ).all()

    items: list[PoliticianListItem] = []
    for person_record in people:
        membership = _current_membership(person_record)
        items.append(
            PoliticianListItem(
                slug=person_record.slug,
                full_name=person_record.full_name,
                chamber=person_record.chamber.slug if person_record.chamber else None,
                image_url=person_record.image_url,
                email=person_record.email,
                current_membership=MembershipSummary(
                    party=(
                        None
                        if not membership or not membership.party
                        else {
                            "name": membership.party.name_en,
                            "short_name": membership.party.short_name,
                            "slug": membership.party.slug,
                            "color": membership.party.color,
                        }
                    ),
                    riding_name=membership.riding_name if membership else None,
                    region_name=membership.region_name if membership else None,
                    province_code=membership.province_code if membership else None,
                    role_title=membership.role_title if membership else None,
                    is_current=membership.is_current if membership else True,
                    started_on=membership.started_on if membership else None,
                    ended_on=membership.ended_on if membership else None,
                )
                if membership
                else None,
            )
        )

    return {
        "items": [item.model_dump() for item in items],
        "meta": PageMeta(total=total, limit=limit, offset=offset).model_dump(),
    }


@router.get("/{slug}", response_model=PoliticianDetail)
def get_politician(slug: str, db: Session = Depends(get_db)) -> PoliticianDetail:
    person_record = db.scalar(
        select(Person)
        .where(Person.slug == slug)
        .options(
            selectinload(Person.memberships).selectinload(PersonMembership.party),
            selectinload(Person.committee_memberships).selectinload(CommitteeMembership.committee),
            selectinload(Person.chamber),
        )
    )
    if person_record is None:
        raise HTTPException(status_code=404, detail="Politician not found")

    stats_row = db.scalar(
        select(PersonStats)
        .join(LegislatureSession, PersonStats.session_id == LegislatureSession.id)
        .where(PersonStats.person_id == person_record.id)
        .order_by(
            LegislatureSession.parliament_number.desc(),
            LegislatureSession.session_number.desc(),
        )
        .limit(1)
    )
    sponsored_bill_numbers = list(
        db.scalars(
            select(Bill.number)
            .where(Bill.sponsor_person_id == person_record.id)
            .order_by(Bill.introduced_on.desc().nullslast())
        )
    )

    current_membership = _current_membership(person_record)
    memberships = [
        MembershipSummary(
            party=(
                None
                if not membership.party
                else {
                    "name": membership.party.name_en,
                    "short_name": membership.party.short_name,
                    "slug": membership.party.slug,
                    "color": membership.party.color,
                }
            ),
            riding_name=membership.riding_name,
            region_name=membership.region_name,
            province_code=membership.province_code,
            role_title=membership.role_title,
            is_current=membership.is_current,
            started_on=membership.started_on,
            ended_on=membership.ended_on,
        )
        for membership in person_record.memberships
    ]

    return PoliticianDetail(
        slug=person_record.slug,
        full_name=person_record.full_name,
        chamber=person_record.chamber.slug if person_record.chamber else None,
        image_url=person_record.image_url,
        email=person_record.email,
        current_membership=(
            MembershipSummary(
                party=(
                    None
                    if not current_membership or not current_membership.party
                    else {
                        "name": current_membership.party.name_en,
                        "short_name": current_membership.party.short_name,
                        "slug": current_membership.party.slug,
                        "color": current_membership.party.color,
                    }
                ),
                riding_name=current_membership.riding_name if current_membership else None,
                region_name=current_membership.region_name if current_membership else None,
                province_code=current_membership.province_code if current_membership else None,
                role_title=current_membership.role_title if current_membership else None,
                is_current=current_membership.is_current if current_membership else True,
                started_on=current_membership.started_on if current_membership else None,
                ended_on=current_membership.ended_on if current_membership else None,
            )
            if current_membership
            else None
        ),
        bio_en=person_record.bio_en,
        bio_fr=person_record.bio_fr,
        memberships=memberships,
        committees=[
            CommitteeMembershipSummary(
                committee_slug=membership.committee.slug,
                committee_name=membership.committee.name_en,
                role=membership.role,
            )
            for membership in person_record.committee_memberships
        ],
        sponsored_bill_numbers=sponsored_bill_numbers,
        stats=PoliticianVoteStats(
            votes_attended_pct=stats_row.attendance_pct if stats_row else None,
            party_line_voting_pct=stats_row.party_line_pct if stats_row else None,
            free_vote_participation_pct=None,
            votes_eligible=stats_row.votes_eligible if stats_row else None,
            votes_cast=stats_row.votes_cast if stats_row else None,
            dissent_count=stats_row.dissent_count if stats_row else None,
        ),
    )
