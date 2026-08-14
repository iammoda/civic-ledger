from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.models.base import Base, TimestampMixin, utcnow


class Jurisdiction(Base, TimestampMixin):
    __tablename__ = "jurisdictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name_en: Mapped[str] = mapped_column(String(255))
    name_fr: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), default="CA")
    # federal | provincial | municipal
    level: Mapped[str] = mapped_column(String(16), default="federal", server_default="federal")

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
    # Office contact blocks (constituency/legislature phone + address) for
    # provincial/municipal reps synced from Represent.
    offices_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
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
    legisinfo_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    legisinfo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary_source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    text_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Library of Parliament short legislative summary (human-written,
    # attributed) and the bill's full text for search — no AI involved.
    official_summary_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Machine-readable LEGISinfo status code, e.g. "RoyalAssentGiven".
    status_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_law: Mapped[bool] = mapped_column(Boolean, default=False)
    # Lifecycle outcome: pending | enacted | defeated_vote | died_committee |
    # died_order_paper | died_senate | withdrawn | not_proceeded_with
    outcome: Mapped[str] = mapped_column(String(32), default="pending", index=True)

    session: Mapped[LegislatureSession] = relationship(back_populates="bills")
    chamber: Mapped[Chamber] = relationship(back_populates="bills")
    sponsor: Mapped[Person | None] = relationship()
    votes: Mapped[list["Vote"]] = relationship(back_populates="bill")
    text_sources: Mapped[list["BillTextSource"]] = relationship(back_populates="bill")
    analyses: Mapped[list["AnalysisResult"]] = relationship(back_populates="bill")
    death: Mapped["BillDeath | None"] = relationship(back_populates="bill", uselist=False)

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
    # Direction normalization (Phase 2 fills these): what a Yea ballot means
    # for the underlying matter — "advance" | "block" | None (unknown).
    yea_effect: Mapped[str | None] = mapped_column(String(16), nullable=True)
    plain_meaning_en: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class BillDeath(Base, TimestampMixin):
    """How a bill died and who is attributable. One row per dead bill."""

    __tablename__ = "bill_deaths"

    id: Mapped[int] = mapped_column(primary_key=True)
    bill_id: Mapped[int] = mapped_column(ForeignKey("bills.id"), unique=True, index=True)
    # defeated_vote | died_committee | died_order_paper | died_senate |
    # withdrawn | not_proceeded_with
    mechanism: Mapped[str] = mapped_column(String(32), index=True)
    # Legislative stage at death, e.g. "second-reading", "committee", "senate".
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    # The recorded division that killed it, if any.
    kill_vote_id: Mapped[int | None] = mapped_column(ForeignKey("votes.id"), nullable=True, index=True)
    committee_id: Mapped[int | None] = mapped_column(ForeignKey("committees.id"), nullable=True, index=True)
    # Neutral, factual attribution note ("Died when Parliament was dissolved
    # on ...", "Defeated at second reading 152-128").
    attribution_en: Mapped[str | None] = mapped_column(Text, nullable=True)

    bill: Mapped[Bill] = relationship(back_populates="death")
    kill_vote: Mapped[Vote | None] = relationship()
    committee: Mapped[Committee | None] = relationship()


class PersonRole(Base, TimestampMixin):
    """Cabinet/critic/officer roles over time — who is responsible for what."""

    __tablename__ = "person_roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), index=True)
    # minister | parliamentary_secretary | critic | house_officer
    role_type: Mapped[str] = mapped_column(String(32), index=True)
    title_en: Mapped[str] = mapped_column(String(255))
    title_fr: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Normalized portfolio slug, e.g. "housing", "finance" — joinable to topics.
    portfolio_slug: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    person: Mapped[Person] = relationship()

    __table_args__ = (
        UniqueConstraint("person_id", "role_type", "title_en", "started_on", name="uq_person_role"),
    )


class RepresentationEvent(Base, TimestampMixin):
    """Notable representation changes: floor crossings, resignations, deaths."""

    __tablename__ = "representation_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), index=True)
    # floor_crossing | resignation | death | elected | seat_vacated
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    occurred_on: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    from_party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"), nullable=True)
    to_party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"), nullable=True)
    details_en: Mapped[str | None] = mapped_column(Text, nullable=True)

    person: Mapped[Person] = relationship()
    from_party: Mapped[Party | None] = relationship(foreign_keys=[from_party_id])
    to_party: Mapped[Party | None] = relationship(foreign_keys=[to_party_id])

    __table_args__ = (
        UniqueConstraint("person_id", "event_type", "occurred_on", name="uq_representation_event"),
    )


class Topic(Base, TimestampMixin):
    """Curated topic taxonomy (~25-30 topics) users can follow."""

    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name_en: Mapped[str] = mapped_column(String(128))
    name_fr: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Comma-separated colloquial aliases ("carbon tax" -> fuel charge).
    aliases_en: Mapped[str | None] = mapped_column(Text, nullable=True)

    entity_links: Mapped[list["EntityTopic"]] = relationship(back_populates="topic")


class EntityTopic(Base, TimestampMixin):
    """Polymorphic link of content (bill/vote/petition/...) to a topic."""

    __tablename__ = "entity_topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # How the link was made: llm | subject_code | manual
    source: Mapped[str] = mapped_column(String(32), default="llm")

    topic: Mapped[Topic] = relationship(back_populates="entity_links")

    __table_args__ = (
        UniqueConstraint("topic_id", "entity_type", "entity_id", name="uq_entity_topic"),
    )


class Embedding(Base, TimestampMixin):
    """pgvector embedding for any entity; powers search/Ask/topic matching."""

    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    # Hash of the embedded text — re-embed only when content changes.
    content_hash: Mapped[str] = mapped_column(String(64))
    model_name: Mapped[str] = mapped_column(String(128))
    vector: Mapped[list[float]] = mapped_column(Vector(1536))

    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", name="uq_embedding_entity"),
    )


class Document(Base, TimestampMixin):
    """Provenance record for any ingested source document."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_system: Mapped[str] = mapped_column(String(64), index=True)
    source_url: Mapped[str] = mapped_column(String(1000))
    document_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class PersonStats(Base, TimestampMixin):
    """Derived accountability stats per person per session (nightly job)."""

    __tablename__ = "person_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("legislature_sessions.id"), index=True)
    votes_eligible: Mapped[int] = mapped_column(Integer, default=0)
    votes_cast: Mapped[int] = mapped_column(Integer, default=0)
    attendance_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    party_line_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    dissent_count: Mapped[int] = mapped_column(Integer, default=0)
    computed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    person: Mapped[Person] = relationship()
    session: Mapped[LegislatureSession] = relationship()

    __table_args__ = (
        UniqueConstraint("person_id", "session_id", name="uq_person_stats_session"),
    )


class LlmUsage(Base, TimestampMixin):
    """Cost ledger: one row per LLM call. Powers the spend dashboard and
    the hard monthly budget cap."""

    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_name: Mapped[str] = mapped_column(String(128), index=True)
    job_name: Mapped[str] = mapped_column(String(128), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6, asdecimal=False), default=0.0)


class GlossaryTerm(Base, TimestampMixin):
    """Plain-language definitions for parliamentary/legal jargon."""

    __tablename__ = "glossary_terms"

    id: Mapped[int] = mapped_column(primary_key=True)
    term: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    definition_en: Mapped[str] = mapped_column(Text)
    definition_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Readability grade of the definition (Flesch-Kincaid).
    reading_grade: Mapped[float | None] = mapped_column(Float, nullable=True)


class LobbyOrgProfile(Base, TimestampMixin):
    """One-line description of an organization that lobbies parliamentarians.

    Generated by the LLM (budget-gated, cached forever) so a visitor knows
    what "Jack.org" or "Imagine Canada" actually is. Descriptive only —
    never characterizes the lobbying itself.
    """

    __tablename__ = "lobby_org_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_name: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    # pending | published | blocked (mirrors AnalysisResult semantics).
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)


class Petition(Base, TimestampMixin):
    """House of Commons e-petition (official petitions.ourcommons.ca)."""

    __tablename__ = "petitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(16), unique=True, index=True)  # "e-7601"
    title_en: Mapped[str] = mapped_column(String(500))  # Subject line
    text_en: Mapped[str | None] = mapped_column(Text, nullable=True)  # Prayer text
    # Raw status from the site + normalized state: open | closed
    status_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str] = mapped_column(String(16), default="open", index=True)
    closes_at: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    signature_count: Mapped[int] = mapped_column(Integer, default=0)
    # Official subject keywords, comma-separated (from the HoC index).
    keywords_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    sponsor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sponsor_person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True, index=True)
    parliament_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str] = mapped_column(String(500))

    sponsor: Mapped[Person | None] = relationship()


class Organization(Base, TimestampMixin):
    """A company/org appearing in lobbying or contribution records."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(500), index=True)
    normalized_name: Mapped[str] = mapped_column(String(500), unique=True, index=True)

    lobby_communications: Mapped[list["LobbyCommunication"]] = relationship(back_populates="client_org")


class LobbyCommunication(Base, TimestampMixin):
    """One communication report from the Registry of Lobbyists: a lobbyist
    (for a client org) contacted a designated public office holder."""

    __tablename__ = "lobby_communications"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Registry communication number, e.g. "12345-selection" per DPOH row.
    source_ref: Mapped[str] = mapped_column(String(64), index=True)
    comm_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    client_org_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    client_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    registrant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dpoh_name: Mapped[str] = mapped_column(String(255), index=True)
    dpoh_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    institution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Matched MP/senator, when the DPOH is a parliamentarian we track.
    dpoh_person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True, index=True)
    # Registry subject-matter codes, comma-separated (official taxonomy).
    subjects: Mapped[str | None] = mapped_column(Text, nullable=True)

    client_org: Mapped[Organization | None] = relationship(back_populates="lobby_communications")
    dpoh_person: Mapped[Person | None] = relationship()

    __table_args__ = (
        UniqueConstraint("source_ref", "dpoh_name", name="uq_lobby_comm_ref_dpoh"),
    )


class Contribution(Base, TimestampMixin):
    """A political contribution (Elections Canada financial returns)."""

    __tablename__ = "contributions"

    id: Mapped[int] = mapped_column(primary_key=True)
    contributor_name: Mapped[str] = mapped_column(String(255), index=True)
    normalized_contributor: Mapped[str] = mapped_column(String(255), index=True)
    contributor_city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contributor_province: Mapped[str | None] = mapped_column(String(8), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2, asdecimal=False), default=0.0)
    received_on: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    recipient_name: Mapped[str] = mapped_column(String(255), index=True)
    recipient_party: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recipient_person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True, index=True)
    # e.g. "candidate", "party", "riding_association"
    recipient_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    recipient_person: Mapped[Person | None] = relationship()


class IntegrityFlag(Base, TimestampMixin):
    """A pattern-detector finding. NOTHING publishes without human review:
    status pending_review -> published | dismissed (admin decision)."""

    __tablename__ = "integrity_flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    detector: Mapped[str] = mapped_column(String(64), index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True, index=True)
    bill_id: Mapped[int | None] = mapped_column(ForeignKey("bills.id"), nullable=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    # Neutral factual headline + detail. Never accusatory language.
    headline_en: Mapped[str] = mapped_column(String(500))
    detail_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Evidence: structured references to the underlying records.
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # Dedupe key so re-running detectors doesn't duplicate flags.
    fingerprint: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending_review", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    person: Mapped[Person | None] = relationship()
    bill: Mapped["Bill | None"] = relationship()
    organization: Mapped[Organization | None] = relationship()


class Correction(Base, TimestampMixin):
    """Public corrections/dispute submissions (in-app; no email)."""

    __tablename__ = "corrections"

    id: Mapped[int] = mapped_column(primary_key=True)
    page_url: Mapped[str] = mapped_column(String(1000))
    message: Mapped[str] = mapped_column(Text)
    contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExpenseSummary(Base, TimestampMixin):
    """Quarterly expense totals per MP (HoC Proactive Disclosure summary CSV)."""

    __tablename__ = "expense_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True, index=True)
    mp_name_raw: Mapped[str] = mapped_column(String(255), index=True)  # "Alghabra, Hon. Omar"
    constituency: Mapped[str | None] = mapped_column(String(255), nullable=True)
    caucus: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)  # e.g. 2025 = FY2025-26 page year
    quarter: Mapped[int] = mapped_column(Integer, index=True)  # 1-4
    salaries: Mapped[float] = mapped_column(Numeric(14, 2, asdecimal=False), default=0.0)
    travel: Mapped[float] = mapped_column(Numeric(14, 2, asdecimal=False), default=0.0)
    hospitality: Mapped[float] = mapped_column(Numeric(14, 2, asdecimal=False), default=0.0)
    contracts: Mapped[float] = mapped_column(Numeric(14, 2, asdecimal=False), default=0.0)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    person: Mapped[Person | None] = relationship()

    __table_args__ = (
        UniqueConstraint("mp_name_raw", "fiscal_year", "quarter", name="uq_expense_summary_mp_quarter"),
    )


class ExpenseItem(Base, TimestampMixin):
    """One expense line item (travel claim / hospitality event / contract)."""

    __tablename__ = "expense_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True, index=True)
    mp_name_raw: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(16), index=True)  # travel|hospitality|contract
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)
    quarter: Mapped[int] = mapped_column(Integer, index=True)
    supplier: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_on: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2, asdecimal=False), default=0.0, index=True)
    # Travel-specific context
    traveller_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    traveller_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    purpose: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    claim_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_url: Mapped[str] = mapped_column(String(500))
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    person: Mapped[Person | None] = relationship()
    organization: Mapped[Organization | None] = relationship()


# --- Municipal meeting record (eScribe et al.) ------------------------------


class Meeting(Base, TimestampMixin):
    """One sitting of a municipal body (Council, General Committee, ...).

    source_id is "{tenant}:{meeting-guid}" for eScribe. minutes_url always
    points at the primary source — transparency requires every datum to be
    one click from the official record.
    """

    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True)
    chamber_id: Mapped[int] = mapped_column(ForeignKey("chambers.id"), index=True)
    body_name: Mapped[str] = mapped_column(String(255))  # "Council", "General Committee"
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meeting_date: Mapped[date] = mapped_column(Date, index=True)
    source_system: Mapped[str] = mapped_column(String(32), default="escribe")
    source_id: Mapped[str] = mapped_column(String(128))
    minutes_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Set once minutes were successfully parsed (attendance found).
    minutes_parsed: Mapped[bool] = mapped_column(Boolean, default=False)

    chamber: Mapped[Chamber] = relationship()
    attendance: Mapped[list["MeetingAttendance"]] = relationship(back_populates="meeting")
    motions: Mapped[list["Motion"]] = relationship(back_populates="meeting")

    __table_args__ = (UniqueConstraint("source_system", "source_id", name="uq_meeting_source"),)


class MeetingAttendance(Base, TimestampMixin):
    __tablename__ = "meeting_attendance"

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), index=True)
    # present | absent | regrets
    status: Mapped[str] = mapped_column(String(16), default="present")
    # Raw name as printed in the minutes (provenance/debugging).
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    meeting: Mapped[Meeting] = relationship(back_populates="attendance")
    person: Mapped[Person] = relationship()

    __table_args__ = (UniqueConstraint("meeting_id", "person_id", name="uq_attendance_meeting_person"),)


class Motion(Base, TimestampMixin):
    """A motion/resolution inside a meeting, with mover/seconder and result.

    When the minutes include per-member votes (MotionVoters), those land in
    the shared Vote/Ballot tables and vote_id links back here.
    """

    __tablename__ = "motions"

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0)  # Order within minutes.
    resolution_number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    item_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    item_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    text_en: Mapped[str] = mapped_column(Text, default="")
    mover_person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True, index=True)
    seconder_person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True, index=True)
    # carried | lost | referred | withdrawn | unknown
    result: Mapped[str] = mapped_column(String(32), default="unknown")
    vote_id: Mapped[int | None] = mapped_column(ForeignKey("votes.id"), nullable=True, index=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    meeting: Mapped[Meeting] = relationship(back_populates="motions")
    mover: Mapped[Person | None] = relationship(foreign_keys=[mover_person_id])
    seconder: Mapped[Person | None] = relationship(foreign_keys=[seconder_person_id])
    vote: Mapped["Vote | None"] = relationship()

    __table_args__ = (UniqueConstraint("meeting_id", "sequence", name="uq_motion_meeting_sequence"),)


class ConflictDeclaration(Base, TimestampMixin):
    """Declared conflicts of interest, parsed from the minutes section.

    person_id stays NULL when the name can't be matched — the raw text is
    kept either way, because losing a declaration would be the opposite of
    the point.
    """

    __tablename__ = "conflict_declarations"

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True, index=True)
    person_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")

    meeting: Mapped[Meeting] = relationship()
    person: Mapped[Person | None] = relationship()

    __table_args__ = (UniqueConstraint("meeting_id", "person_name", "note", name="uq_declaration_meeting_person_note"),)
