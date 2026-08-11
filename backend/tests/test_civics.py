"""Tests: committees, ministers, Ask minister card, question follows, glossary."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

import app.services.ask as ask_mod
from app.data.glossary import TERMS, seed_glossary
from app.data.topics import seed_topics
from app.ingestion.committee_members import parse_member_names
from app.ingestion.ministry import parse_ministry_tiles, portfolio_topic_slug, sync_ministers
from app.ingestion.sync import SyncContext
from app.llm.readability import HARD_CEILING
from app.models import (
    Bill,
    EntityTopic,
    GlossaryTerm,
    Notification,
    Person,
    PersonRole,
    Topic,
    UserFollow,
)
from app.services.ask import ask
from app.services.notifications import match_notifications
from test_search_ask import UnconfiguredLLM

FIXTURES = Path(__file__).parent / "fixtures"


# --- Committee member parsing ---


def test_parse_committee_member_names_real_fixture() -> None:
    html = (FIXTURES / "committee_members.html").read_text()
    names = parse_member_names(html)
    assert len(names) >= 5
    assert "Michael Barrett" in names
    assert len(names) == len(set(names))  # Deduped (desktop+mobile cards).


# --- Ministry parsing + sync ---


def test_parse_ministry_tiles_real_fixture() -> None:
    html = (FIXTURES / "ministries.html").read_text()
    ministers = parse_ministry_tiles(html)
    assert ministers
    carney = next(m for m in ministers if m["name"] == "Mark Carney")
    assert carney["title"] == "Prime Minister"
    assert carney["constituency"] == "Nepean"


def test_portfolio_topic_mapping() -> None:
    assert portfolio_topic_slug("Minister of Housing and Infrastructure") == "housing"
    assert portfolio_topic_slug("Minister of Health") == "healthcare"
    assert portfolio_topic_slug("Minister of Finance and National Revenue") == "taxes"
    assert portfolio_topic_slug("President of the Treasury Board") is None


def test_sync_ministers_upserts_and_end_dates(db) -> None:
    ctx = SyncContext(db)
    jane = Person(slug="jane-doe", full_name="Jane Doe", chamber_id=ctx.house.id)
    bob = Person(slug="bob-roe", full_name="Bob Roe", chamber_id=ctx.house.id)
    db.add_all([jane, bob])
    db.commit()
    seed_topics(db)

    html_v1 = """
    <div class="ce-mip-mp-tile-container">
      <div class="ce-mip-mp-name">Jane Doe</div><div>Minister of Health</div>
      <div class="ce-mip-mp-constituency">Testville</div>
    </div>
    <div class="ce-mip-mp-tile-container">
      <div class="ce-mip-mp-name">Bob Roe</div><div>Minister of Finance</div>
      <div class="ce-mip-mp-constituency">Otherville</div>
    </div>
    """
    assert sync_ministers(db, html_v1) == 2
    role = db.scalar(select(PersonRole).where(PersonRole.person_id == jane.id))
    assert role.title_en == "Minister of Health"
    assert role.portfolio_slug == "healthcare"
    assert role.is_current is True

    # Shuffle: Bob is out; Jane keeps her role.
    html_v2 = """
    <div class="ce-mip-mp-tile-container">
      <div class="ce-mip-mp-name">Jane Doe</div><div>Minister of Health</div>
    </div>
    """
    assert sync_ministers(db, html_v2) == 0  # No new roles.
    bob_role = db.scalar(select(PersonRole).where(PersonRole.person_id == bob.id))
    assert bob_role.is_current is False
    assert bob_role.ended_on == date.today()
    jane_role = db.scalar(select(PersonRole).where(PersonRole.person_id == jane.id))
    assert jane_role.is_current is True


# --- Ask responsible-minister resolution ---


async def test_ask_resolves_responsible_minister(db, monkeypatch) -> None:
    monkeypatch.setattr(ask_mod, "LLMClient", UnconfiguredLLM)
    ctx = SyncContext(db)
    seed_topics(db)
    session = ctx.session_for_label("45-1")
    minister = Person(slug="jane-doe", full_name="Jane Doe", chamber_id=ctx.house.id)
    db.add(minister)
    db.flush()
    db.add(
        PersonRole(
            person_id=minister.id, role_type="minister",
            title_en="Minister of Housing and Infrastructure",
            portfolio_slug="housing", is_current=True,
        )
    )
    bill = Bill(
        session_id=session.id, chamber_id=ctx.house.id, number="C-56",
        title_en="An Act respecting affordable housing",
    )
    db.add(bill)
    db.flush()
    housing = db.scalar(select(Topic).where(Topic.slug == "housing"))
    db.add(EntityTopic(topic_id=housing.id, entity_type="bill", entity_id=bill.id, source="alias"))
    db.commit()

    response = await ask(db, "I can't afford housing anymore")
    assert response.minister is not None
    assert response.minister.name == "Jane Doe"
    assert response.minister.title == "Minister of Housing and Infrastructure"


# --- Question follows ---


def test_question_follow_matches_new_bills_by_keywords(db) -> None:
    ctx = SyncContext(db)
    seed_topics(db)
    session = ctx.session_for_label("45-1")
    bill = Bill(
        session_id=session.id, chamber_id=ctx.house.id, number="C-77",
        title_en="An Act respecting rent and affordable housing supply",
    )
    unrelated = Bill(
        session_id=session.id, chamber_id=ctx.house.id, number="C-78",
        title_en="An Act to amend the Fisheries Act",
    )
    db.add_all([bill, unrelated])
    db.commit()

    db.add(UserFollow(user_id="u1", target_type="question", target_ref="why is rent so high in housing markets"))
    db.commit()

    created = match_notifications(db)
    notifications = db.scalars(select(Notification).where(Notification.kind == "question_match")).all()
    assert len(notifications) == 1
    assert "C-77" in notifications[0].body_en
    assert "rent so high" in notifications[0].title_en
    # Idempotent.
    assert match_notifications(db) == 0


# --- Glossary ---


def test_glossary_seed_idempotent_and_readable(db) -> None:
    created = seed_glossary(db)
    assert created == len(TERMS)
    assert seed_glossary(db) == 0  # Idempotent.

    rows = db.scalars(select(GlossaryTerm)).all()
    assert len(rows) == len(TERMS)
    # Every hand-written definition must clear our own readability bar.
    too_complex = [(r.term, r.reading_grade) for r in rows if (r.reading_grade or 0) > HARD_CEILING]
    assert not too_complex, f"definitions above grade {HARD_CEILING}: {too_complex}"
    prorogation = db.scalar(select(GlossaryTerm).where(GlossaryTerm.term == "prorogation"))
    assert "dies" in prorogation.definition_en
