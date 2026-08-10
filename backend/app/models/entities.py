from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utcnow


class Jurisdiction(Base, TimestampMixin):
    __tablename__ = "jurisdictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name_en: Mapped[str] = mapped_column(String(255))
    name_fr: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), default="CA")

    chambers: Mapped[list["Chamber"]] = relationship(back_populates="jurisdiction")
    sessions: Mapped[list["LegislatureSession"]] = relationship(back_populates="jurisdiction")


class Chamber(Base, TimestampMixin):
    __tablename__ = "chambers"

    id: Mapped[int] = mapped_column(primary_key=True)
    jurisdiction_id: Mapped[int] = mapped_column(ForeignKey("jurisdictions.id"), index=True)
    slug: Mapped[str] = mapped_column(String(32), index=True)
    name_en: Mapped[str] = mapped_column(String(255))
    name_fr: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_elected: Mapped[bool] = mapped_column(Boolean, default=True)

    jurisdiction: Mapped[Jurisdiction] = relationship(back_populates="chambers")
    people: Mapped[list["Person"]] = relationship(back_populates="chamber")
    bills: Mapped[list["Bill"]] = relationship(back_populates="chamber")
    votes: Mapped[list["Vote"]] = relationship(back_populates="chamber")
    debates: Mapped[list["Debate"]] = relationship(back_populates="chamber")

    __table_args__ = (UniqueConstraint("jurisdiction_id", "slug", name="uq_chamber_jurisdiction_slug"),)


class LegislatureSession(Base, TimestampMixin):
    __tablename__ = "legislature_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    jurisdiction_id: Mapped[int] = mapped_column(ForeignKey("jurisdictions.id"), index=True)
    parliament_number: Mapped[int] = mapped_column(Integer)
    session_number: Mapped[int] = mapped_column(Integer)
    started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)

    jurisdiction: Mapped[Jurisdiction] = relationship(back_populates="sessions")
    bills: Mapped[list["Bill"]] = relationship(back_populates="session")
    votes: Mapped[list["Vote"]] = relationship(back_populates="session")

    __table_args__ = (
        UniqueConstraint(
            "jurisdiction_id",
            "parliament_number",
            "session_number",
            name="uq_session_jurisdiction_numbers",
        ),
    )

    @property
    def label(self) -> str:
        return f"{self.parliament_number}-{self.session_number}"


class Party(Base, TimestampMixin):
    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(primary_key=True)
    jurisdiction_id: Mapped[int] = mapped_column(ForeignKey("jurisdictions.id"), index=True)
    name_en: Mapped[str] = mapped_column(String(255))
    name_fr: Mapped[str | None] = mapped_column(String(255), nullable=True)
    short_name: Mapped[str] = mapped_column(String(64), index=True)
    slug: Mapped[str] = mapped_column(String(64), index=True)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)

    members: Mapped[list["PersonMembership"]] = relationship(back_populates="party")

    __table_args__ = (UniqueConstraint("jurisdiction_id", "slug", name="uq_party_jurisdiction_slug"),)


class Person(Base, TimestampMixin):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True)
    chamber_id: Mapped[int | None] = mapped_column(ForeignKey("chambers.id"), nullable=True, index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    given_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    family_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    honorific: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bio_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_system: Mapped[str] = mapped_column(String(64), default="manual")
    source_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    chamber: Mapped[Chamber | None] = relationship(back_populates="people")
    memberships: Mapped[list["PersonMembership"]] = relationship(back_populates="person")
    ballots: Mapped[list["Ballot"]] = relationship(back_populates="person")
    committee_memberships: Mapped[list["CommitteeMembership"]] = relationship(back_populates="person")


class PersonMembership(Base, TimestampMixin):
    __tablename__ = "person_memberships"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), index=True)
    party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"), nullable=True, index=True)
    chamber_id: Mapped[int | None] = mapped_column(ForeignKey("chambers.id"), nullable=True, index=True)
    riding_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    province_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    role_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)

    person: Mapped[Person] = relationship(back_populates="memberships")
    party: Mapped[Party | None] = relationship(back_populates="members")


class Bill(Base, TimestampMixin):
    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("legislature_sessions.id"), index=True)
    chamber_id: Mapped[int] = mapped_column(ForeignKey("chambers.id"), index=True)
    sponsor_person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True, index=True)
    number: Mapped[str] = mapped_column(String(64), index=True)
    short_title_en: Mapped[str | None] = mapped_column(String(500), nullable=True)
    short_title_fr: Mapped[str | None] = mapped_column(String(500), nullable=True)
    title_en: Mapped[str] = mapped_column(String(500))
    title_fr: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status_fr: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bill_type: Mapped[str] = mapped_column(String(32), default="government")
    is_omnibus: Mapped[bool] = mapped_column(Boolean, default=False)
    introduced_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    legisinfo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary_source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    session: Mapped[LegislatureSession] = relationship(back_populates="bills")
    chamber: Mapped[Chamber] = relationship(back_populates="bills")
    sponsor: Mapped[Person | None] = relationship()
    votes: Mapped[list["Vote"]] = relationship(back_populates="bill")
    text_sources: Mapped[list["BillTextSource"]] = relationship(back_populates="bill")
    analyses: Mapped[list["AnalysisResult"]] = relationship(back_populates="bill")

    __table_args__ = (UniqueConstraint("session_id", "number", "chamber_id", name="uq_bill_session_number_chamber"),)


class BillTextSource(Base, TimestampMixin):
    __tablename__ = "bill_text_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    bill_id: Mapped[int] = mapped_column(ForeignKey("bills.id"), index=True)
    language: Mapped[str] = mapped_column(String(2), default="en")
    source_url: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(64), default="html")
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)

    bill: Mapped[Bill] = relationship(back_populates="text_sources")


class Vote(Base, TimestampMixin):
    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("legislature_sessions.id"), index=True)
    chamber_id: Mapped[int] = mapped_column(ForeignKey("chambers.id"), index=True)
    bill_id: Mapped[int | None] = mapped_column(ForeignKey("bills.id"), nullable=True, index=True)
    number: Mapped[str] = mapped_column(String(64), index=True)
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    description_en: Mapped[str] = mapped_column(Text)
    description_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    yea_total: Mapped[int] = mapped_column(Integer, default=0)
    nay_total: Mapped[int] = mapped_column(Integer, default=0)
    paired_total: Mapped[int] = mapped_column(Integer, default=0)
    vote_type: Mapped[str] = mapped_column(String(32), default="whipped")
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    session: Mapped[LegislatureSession] = relationship(back_populates="votes")
    chamber: Mapped[Chamber] = relationship(back_populates="votes")
    bill: Mapped[Bill | None] = relationship(back_populates="votes")
    ballots: Mapped[list["Ballot"]] = relationship(back_populates="vote")

    __table_args__ = (UniqueConstraint("session_id", "chamber_id", "number", name="uq_vote_session_chamber_number"),)


class Ballot(Base, TimestampMixin):
    __tablename__ = "ballots"

    id: Mapped[int] = mapped_column(primary_key=True)
    vote_id: Mapped[int] = mapped_column(ForeignKey("votes.id"), index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), index=True)
    ballot: Mapped[str] = mapped_column(String(32))
    party_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
    broke_party_line: Mapped[bool] = mapped_column(Boolean, default=False)

    vote: Mapped[Vote] = relationship(back_populates="ballots")
    person: Mapped[Person] = relationship(back_populates="ballots")

    __table_args__ = (UniqueConstraint("vote_id", "person_id", name="uq_ballot_vote_person"),)


class Committee(Base, TimestampMixin):
    __tablename__ = "committees"

    id: Mapped[int] = mapped_column(primary_key=True)
    chamber_id: Mapped[int] = mapped_column(ForeignKey("chambers.id"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("legislature_sessions.id"), nullable=True, index=True)
    slug: Mapped[str] = mapped_column(String(128), index=True)
    name_en: Mapped[str] = mapped_column(String(255))
    name_fr: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    chamber: Mapped[Chamber] = relationship()
    memberships: Mapped[list["CommitteeMembership"]] = relationship(back_populates="committee")
    events: Mapped[list["CommitteeEvent"]] = relationship(back_populates="committee")

    __table_args__ = (UniqueConstraint("chamber_id", "slug", name="uq_committee_chamber_slug"),)


class CommitteeMembership(Base, TimestampMixin):
    __tablename__ = "committee_memberships"

    id: Mapped[int] = mapped_column(primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), index=True)
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)

    committee: Mapped[Committee] = relationship(back_populates="memberships")
    person: Mapped[Person] = relationship(back_populates="committee_memberships")

    __table_args__ = (UniqueConstraint("committee_id", "person_id", name="uq_committee_membership"),)


class CommitteeEvent(Base, TimestampMixin):
    __tablename__ = "committee_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), index=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    event_type: Mapped[str] = mapped_column(String(64))
    title_en: Mapped[str] = mapped_column(String(500))
    title_fr: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    committee: Mapped[Committee] = relationship(back_populates="events")


class Debate(Base, TimestampMixin):
    __tablename__ = "debates"

    id: Mapped[int] = mapped_column(primary_key=True)
    chamber_id: Mapped[int] = mapped_column(ForeignKey("chambers.id"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("legislature_sessions.id"), nullable=True, index=True)
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    title_en: Mapped[str | None] = mapped_column(String(500), nullable=True)
    title_fr: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    chamber: Mapped[Chamber] = relationship(back_populates="debates")
    speeches: Mapped[list["Speech"]] = relationship(back_populates="debate")

    __table_args__ = (UniqueConstraint("chamber_id", "occurred_on", name="uq_debate_chamber_date"),)


class Speech(Base, TimestampMixin):
    __tablename__ = "speeches"

    id: Mapped[int] = mapped_column(primary_key=True)
    debate_id: Mapped[int] = mapped_column(ForeignKey("debates.id"), index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True, index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    heading_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    heading_fr: Mapped[str | None] = mapped_column(String(255), nullable=True)
    topic_slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_en: Mapped[str] = mapped_column(Text)
    content_fr: Mapped[str | None] = mapped_column(Text, nullable=True)

    debate: Mapped[Debate] = relationship(back_populates="speeches")

    __table_args__ = (UniqueConstraint("debate_id", "sequence", name="uq_speech_debate_sequence"),)


class AnalysisResult(Base, TimestampMixin):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    bill_id: Mapped[int | None] = mapped_column(ForeignKey("bills.id"), nullable=True, index=True)
    debate_id: Mapped[int | None] = mapped_column(ForeignKey("debates.id"), nullable=True, index=True)
    analysis_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    language: Mapped[str] = mapped_column(String(2), default="en")
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    citations: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    bill: Mapped[Bill | None] = relationship(back_populates="analyses")
    debate: Mapped[Debate | None] = relationship()

    __table_args__ = (
        UniqueConstraint("bill_id", "debate_id", "analysis_type", "language", name="uq_analysis_scope_type_language"),
    )


class IngestionRun(Base, TimestampMixin):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_name: Mapped[str] = mapped_column(String(64), index=True)
    job_name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
