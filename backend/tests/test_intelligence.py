"""Phase 2 tests: readability gate, budget cap, direction heuristics,
analysis jobs with a mocked model."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

import app.llm.analyses as analyses_mod
from app.data.topics import seed_topics
from app.ingestion.sync import SyncContext
from app.llm.analyses import (
    analyze_bill,
    heuristic_vote_direction,
    normalize_vote,
    tag_bill_topics,
)
from app.llm.base import StructuredResult
from app.llm.budget import BudgetExceededError, cost_for, ensure_budget, record_usage
from app.llm.readability import meets_gate, reading_grade
from app.models import AnalysisResult, Bill, EntityTopic, LlmUsage, Vote


# --- Readability ---


def test_reading_grade_simple_text_passes_gate() -> None:
    text = "This bill helps people pay rent. It gives money to cities. Cities must build more homes."
    assert reading_grade(text) <= 8.5
    assert meets_gate(text)


def test_reading_grade_complex_text_fails_gate() -> None:
    text = (
        "Notwithstanding the aforementioned considerations, the promulgation of "
        "supplementary regulatory instruments necessitates comprehensive "
        "intergovernmental consultations concerning fiscal equalization methodologies."
    )
    assert not meets_gate(text)


# --- Budget ---


def test_cost_for_known_models() -> None:
    assert cost_for("claude-sonnet-5", 1_000_000, 0) == 3.0
    assert cost_for("claude-haiku-4-5", 0, 1_000_000) == 5.0
    # Unknown models get the safe-high rate.
    assert cost_for("mystery-model", 1_000_000, 0) == 10.0


def test_ensure_budget_raises_when_cap_hit(db) -> None:
    db.add(LlmUsage(model_name="claude-sonnet-5", job_name="x", cost_usd=500.0))
    db.commit()
    with pytest.raises(BudgetExceededError):
        ensure_budget(db)


def test_record_usage_computes_cost(db) -> None:
    result = StructuredResult(data={}, model="claude-haiku-4-5", input_tokens=100_000, output_tokens=10_000)
    row = record_usage(db, result, job_name="test_job", entity_type="bill", entity_id=1)
    assert row.cost_usd == pytest.approx(0.15)
    ensure_budget(db)  # Well under cap — should not raise.


# --- Vote direction heuristics ---


def test_heuristics_advance() -> None:
    assert heuristic_vote_direction("3rd reading and adoption of Bill C-30, An Act...") == "advance"
    assert heuristic_vote_direction("That Bill C-5 be now read a second time") == "advance"
    assert heuristic_vote_direction("Concurrence at report stage of Bill C-2") == "advance"


def test_heuristics_block() -> None:
    assert heuristic_vote_direction("That Bill C-7 be not now read a second time") == "block"
    assert heuristic_vote_direction("this House declines to give second reading... six months hence") == "block"


def test_heuristics_unknown_defers_to_llm() -> None:
    # Amendments to bill motions invert unpredictably — never guessed.
    assert heuristic_vote_direction("Motion respecting Senate amendments to Bill C-9 (amendment)") is None
    # Standalone motions ARE resolved (a Yes adopts the motion itself).
    assert heuristic_vote_direction("Opposition Motion (Automotive strategy)") == "advance"


# --- Jobs with mocked model ---


class FakeLLMClient:
    """Stands in for LLMClient; returns canned schema-valid data."""

    def __init__(self, *, fast: bool = False) -> None:
        self.model = "claude-haiku-4-5" if fast else "claude-sonnet-5"

    def is_configured(self) -> bool:
        return True

    def structured_response(self, *, prompt: str, schema: dict, system: str | None = None, max_tokens: int = 4096) -> StructuredResult:
        props = schema.get("properties", {})
        if "one_sentence" in props:
            data = {
                "one_sentence": "This bill helps people pay rent.",
                "what_it_does": ["It gives money to cities for homes."],
                "who_it_affects": ["Renters and cities."],
                "what_changes": ["More homes get built."],
                "detailed_summary": "This bill gives money to cities. Cities must build more homes.",
                "confidence": 0.9,
            }
        elif "yea_effect" in props:
            data = {"yea_effect": "block", "plain_meaning": "A Yes vote stopped the bill."}
        else:
            data = {"topics": [{"slug": "housing", "confidence": 0.95}]}
        return StructuredResult(data=data, model=self.model, input_tokens=1000, output_tokens=200)


@pytest.fixture()
def fake_llm(monkeypatch):
    monkeypatch.setattr(analyses_mod, "LLMClient", FakeLLMClient)

    async def no_text(db, *, bill_id, text_url):
        return None

    monkeypatch.setattr(analyses_mod, "fetch_bill_text", no_text)


def _make_bill(db) -> Bill:
    ctx = SyncContext(db)
    session = ctx.session_for_label("45-1")
    bill = Bill(
        session_id=session.id,
        chamber_id=ctx.house.id,
        number="C-1",
        title_en="An Act respecting affordable housing",
        status_en="At second reading",
    )
    db.add(bill)
    db.commit()
    return bill


@pytest.mark.asyncio
async def test_analyze_bill_publishes_and_caches(db, fake_llm) -> None:
    bill = _make_bill(db)

    result = await analyze_bill(db, bill.id)
    assert result is not None
    assert result.status == "published"
    assert result.payload["one_sentence"] == "This bill helps people pay rent."
    assert result.payload["reading_grade"] <= 8.5

    usage = db.scalars(select(LlmUsage)).all()
    assert len(usage) == 1  # No readability retry needed.

    # Cache-forever: second call must not spend again.
    again = await analyze_bill(db, bill.id)
    assert again.id == result.id
    assert len(db.scalars(select(LlmUsage)).all()) == 1


@pytest.mark.asyncio
async def test_normalize_vote_heuristic_costs_nothing(db, fake_llm) -> None:
    ctx = SyncContext(db)
    session = ctx.session_for_label("45-1")
    vote = Vote(
        session_id=session.id,
        chamber_id=ctx.house.id,
        number="9",
        occurred_on=date(2026, 5, 1),
        description_en="3rd reading and adoption of Bill C-30",
        result="Passed",
        yea_total=170,
        nay_total=150,
    )
    db.add(vote)
    db.commit()

    updated = await normalize_vote(db, vote.id)
    assert updated.yea_effect == "advance"
    # The sentence names the bill and the stage — never a bare "moved this forward".
    assert "passed Bill C-30 at third reading" in updated.plain_meaning_en
    assert "goes to the Senate" in updated.plain_meaning_en
    assert db.scalars(select(LlmUsage)).all() == []  # Heuristic path is free.


@pytest.mark.asyncio
async def test_normalize_vote_llm_fallback(db, fake_llm) -> None:
    ctx = SyncContext(db)
    session = ctx.session_for_label("45-1")
    vote = Vote(
        session_id=session.id,
        chamber_id=ctx.house.id,
        number="10",
        occurred_on=date(2026, 5, 2),
        description_en="Motion respecting Senate amendments to Bill C-10 (amendment)",
        result="Negatived",
        yea_total=140,
        nay_total=160,
    )
    db.add(vote)
    db.commit()

    updated = await normalize_vote(db, vote.id)
    assert updated.yea_effect == "block"
    assert updated.plain_meaning_en == "A Yes vote stopped the bill."
    assert len(db.scalars(select(LlmUsage)).all()) == 1


@pytest.mark.asyncio
async def test_tag_bill_topics_alias_and_llm(db, fake_llm) -> None:
    bill = _make_bill(db)
    seed_topics(db)

    count = await tag_bill_topics(db, bill.id)
    assert count >= 1

    links = db.scalars(select(EntityTopic)).all()
    slugs = {db.get(analyses_mod.Topic, link.topic_id).slug for link in links}
    assert "housing" in slugs
    llm_links = [link for link in links if link.source == "llm"]
    assert llm_links and llm_links[0].confidence == pytest.approx(0.95)

    # Idempotent: second run does nothing once LLM tags exist.
    assert await tag_bill_topics(db, bill.id) == 0
