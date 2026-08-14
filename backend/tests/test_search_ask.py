"""Phase 3 tests: search fusion, alias expansion, jurisdiction, ask flow."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.services.ask as ask_mod
from app.data.topics import seed_topics
from app.db.session import get_db
from app.ingestion.sync import SyncContext
from app.llm.base import StructuredResult
from app.main import app
from app.models import (
    Bill,
    ExpenseItem,
    LlmUsage,
    Party,
    Person,
    PersonMembership,
    PersonRole,
    Vote,
)
from app.services.ask import ask, heuristic_jurisdiction
from app.services.search import (
    SearchResult,
    expand_query,
    hybrid_search,
    keyword_search,
    rrf_fuse,
)


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _seed_content(db) -> None:
    ctx = SyncContext(db)
    session = ctx.session_for_label("45-1")
    db.add(
        Bill(
            session_id=session.id,
            chamber_id=ctx.house.id,
            number="C-56",
            title_en="An Act respecting affordable housing and groceries",
            short_title_en="Affordable Housing and Groceries Act",
            status_en="At second reading in the House",
        )
    )
    db.add(
        Bill(
            session_id=session.id,
            chamber_id=ctx.house.id,
            number="C-12",
            title_en="An Act to amend the Greenhouse Gas Pollution Pricing Act",
            status_en="In committee",
        )
    )
    db.add(
        Vote(
            session_id=session.id,
            chamber_id=ctx.house.id,
            number="88",
            occurred_on=date(2026, 4, 2),
            description_en="2nd reading of Bill C-56, affordable housing and groceries",
            result="Passed",
            yea_total=177,
            nay_total=140,
        )
    )
    db.commit()


# --- RRF fusion ---


def test_rrf_fusion_orders_by_combined_rank() -> None:
    a1 = SearchResult("bill", 1, "A", "", "/bills/45-1/C-1")
    a2 = SearchResult("bill", 2, "B", "", "/bills/45-1/C-2")
    a3 = SearchResult("vote", 3, "C", "", "/votes/house/45-1/3")
    # Item 2 appears in both lists -> should fuse to the top.
    fused = rrf_fuse([[a1, a2], [a2, a3]])
    assert (fused[0].entity_type, fused[0].entity_id) == ("bill", 2)
    assert len(fused) == 3
    assert fused[0].score > fused[1].score


def test_rrf_respects_limit() -> None:
    results = [SearchResult("bill", i, f"B{i}", "", "/x") for i in range(30)]
    assert len(rrf_fuse([results], limit=5)) == 5


# --- Alias expansion & keyword search (LIKE fallback path) ---


def test_expand_query_bridges_colloquialisms(db) -> None:
    seed_topics(db)
    expanded = expand_query(db, "why am I paying carbon tax")
    assert "Climate & Environment" in expanded
    assert "fuel charge" in expanded


def test_keyword_search_finds_bills_and_votes(db) -> None:
    _seed_content(db)
    results = keyword_search(db, "affordable housing")
    types = {(r.entity_type, r.title.split(" ")[0]) for r in results}
    assert ("bill", "C-56") in types
    assert any(r.entity_type == "vote" for r in results)
    bill_result = next(r for r in results if r.entity_type == "bill" and "C-56" in r.title)
    assert bill_result.url_path == "/bills/45-1/C-56"


async def test_hybrid_search_fallback_without_vectors(db) -> None:
    _seed_content(db)
    results = await hybrid_search(db, "housing")
    assert results and results[0].score > 0


# --- /v1/search: people + expenses sections ---


def test_search_endpoint_returns_people_and_expenses(db, client) -> None:
    _seed_content(db)
    ctx = SyncContext(db)
    party = Party(
        jurisdiction_id=ctx.jurisdiction.id,
        name_en="Liberal Party of Canada",
        short_name="Liberal",
        slug="liberal",
    )
    person = Person(slug="jane-doe", full_name="Jane Doe", chamber_id=ctx.house.id)
    db.add_all([party, person])
    db.flush()
    db.add(
        PersonMembership(
            person_id=person.id,
            party_id=party.id,
            chamber_id=ctx.house.id,
            riding_name="Ottawa Centre",
            province_code="ON",
            is_current=True,
        )
    )
    db.add(
        PersonRole(
            person_id=person.id,
            role_type="minister",
            title_en="Minister of Finance",
            is_current=True,
        )
    )
    db.add(
        ExpenseItem(
            person_id=person.id,
            mp_name_raw="Jane Doe",
            category="travel",
            fiscal_year=2026,
            quarter=1,
            supplier="Air Canada",
            description="Flight Ottawa–Vancouver",
            amount=2345.67,
            source_url="https://www.ourcommons.ca/x",
            fingerprint="fp-jane-travel-1",
        )
    )
    db.commit()

    # Name match hits both the person and their expense line.
    data = client.get("/v1/search", params={"q": "jane doe"}).json()
    assert "results" in data  # Existing shape untouched.
    person_hit = next(p for p in data["people"] if p["slug"] == "jane-doe")
    assert person_hit["full_name"] == "Jane Doe"
    assert person_hit["party_slug"] == "liberal"
    assert person_hit["riding"] == "Ottawa Centre"
    assert person_hit["province_code"] == "ON"
    assert person_hit["level"] == "federal"
    assert person_hit["roles"] == ["Minister of Finance"]
    expense_hit = next(e for e in data["expenses"] if e["supplier"] == "Air Canada")
    assert expense_hit["amount"] == 2345.67
    assert expense_hit["mp_slug"] == "jane-doe"
    assert expense_hit["mp_name"] == "Jane Doe"
    assert expense_hit["category"] == "travel"
    assert expense_hit["source_url"].startswith("https://www.ourcommons.ca")

    # Riding match also surfaces the representative.
    by_riding = client.get("/v1/search", params={"q": "ottawa centre"}).json()
    assert any(p["slug"] == "jane-doe" for p in by_riding["people"])

    # Supplier match surfaces the expense without matching any person.
    by_supplier = client.get("/v1/search", params={"q": "air canada"}).json()
    assert any(e["supplier"] == "Air Canada" for e in by_supplier["expenses"])
    assert all(p["slug"] != "jane-doe" for p in by_supplier["people"])


# --- Jurisdiction heuristics ---


def test_jurisdiction_heuristics() -> None:
    assert heuristic_jurisdiction("My landlord raised my rent 20%").level == "provincial"
    assert heuristic_jurisdiction("I can't find a family doctor").level == "provincial"
    assert heuristic_jurisdiction("The pothole on my street").level == "municipal"
    assert heuristic_jurisdiction("My visa application is stuck").level == "federal"
    assert heuristic_jurisdiction("Something something quantum").level == "unknown"


# --- Ask orchestration ---


class FakeAskLLM:
    def __init__(self, *, fast: bool = False) -> None:
        self.model = "claude-sonnet-5"

    def is_configured(self) -> bool:
        return True

    def structured_response(self, *, prompt: str, schema: dict, system: str | None = None, max_tokens: int = 4096) -> StructuredResult:
        return StructuredResult(
            data={
                "answer_sentence": "Rent rules mostly come from your province, not Ottawa.",
                "answer_detail": "Provinces set rent rules. Federally, Bill C-56 helps build more homes [1].",
                "jurisdiction_level": "provincial",
                "jurisdiction_note": "Housing and tenancy rules are set by provinces.",
                "responsible_ministry": "Housing, Infrastructure and Communities Canada",
                "cited_indexes": [1, 99],  # 99 is invalid — must be filtered.
            },
            model=self.model,
            input_tokens=2000,
            output_tokens=300,
        )


class UnconfiguredLLM:
    def __init__(self, *, fast: bool = False) -> None:
        self.model = "none"

    def is_configured(self) -> bool:
        return False


async def test_ask_generates_cited_answer(db, monkeypatch) -> None:
    _seed_content(db)
    seed_topics(db)
    monkeypatch.setattr(ask_mod, "LLMClient", FakeAskLLM)

    response = await ask(db, "I can't afford rent, who is responsible?")
    assert response.generated is True
    assert response.jurisdiction_level == "provincial"
    assert "province" in response.answer_sentence.lower()
    assert response.evidence  # Retrieved federal evidence.
    assert response.cited_indexes == [1]  # Invalid index filtered out.
    assert db.scalars(select(LlmUsage)).all()  # Usage recorded.


async def test_ask_degrades_without_llm(db, monkeypatch) -> None:
    _seed_content(db)
    monkeypatch.setattr(ask_mod, "LLMClient", UnconfiguredLLM)

    response = await ask(db, "I can't afford rent, who is responsible?")
    assert response.generated is False
    assert response.answer_sentence is None
    assert response.jurisdiction_level == "provincial"  # Heuristic still works.
    assert response.evidence  # Search still works.
    assert db.scalars(select(LlmUsage)).all() == []  # Nothing spent.
