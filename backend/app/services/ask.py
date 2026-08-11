"""Ask: type a problem -> who is responsible, with cited evidence.

Pipeline:
1. Hybrid search retrieves related bills/votes (the evidence pack).
2. Heuristic jurisdiction classifier (free) — Canada-specific keyword map
   for federal / provincial / municipal responsibility.
3. One Sonnet call produces: plain answer (sentence first), refined
   jurisdiction, responsible federal ministry, and evidence citations.
4. Readability gate on the answer; budget cap enforced before the call.

Without an Anthropic key, Ask degrades to search results + heuristic
jurisdiction — honest, never fabricated.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.llm.base import LLMClient
from app.llm.budget import ensure_budget, record_usage
from app.llm.readability import SIMPLIFY_INSTRUCTION, meets_gate, reading_grade
from app.services.search import SearchResult, hybrid_search

NEUTRAL_SYSTEM = (
    "You are a rigorously neutral, non-partisan civic guide for Canadians. "
    "Facts only; no praise or blame. Write for a 12-year-old (reading grade 8 "
    "or below). Only cite evidence from the numbered list provided. If the "
    "evidence does not answer the question, say so plainly."
)

# Free heuristic layer: what level of government owns common problems.
# (level, area) — first match wins; LLM refines when configured.
JURISDICTION_HINTS: list[tuple[tuple[str, ...], str, str]] = [
    (("rent", "landlord", "tenant", "eviction"), "provincial", "housing & tenancy rules"),
    (("doctor", "hospital", "wait time", "surgery", "family physician"), "provincial", "health care delivery"),
    (("school", "teacher", "tuition", "curriculum"), "provincial", "education"),
    (("garbage", "trash", "pothole", "zoning", "transit route", "parking"), "municipal", "local services"),
    (("property tax",), "municipal", "property taxation"),
    (("minimum wage", "workers comp", "workplace safety"), "provincial", "labour standards (most workplaces)"),
    (("ei ", "employment insurance", "cpp", "old age security", "oas", "gis"), "federal", "income supports"),
    (("immigration", "visa", "passport", "refugee", "study permit"), "federal", "immigration"),
    (("carbon tax", "fuel charge", "emissions"), "federal", "carbon pricing"),
    (("bank", "interest rate", "mortgage rules"), "federal", "banking & monetary policy"),
    (("cell phone", "internet bill", "broadband", "crtc"), "federal", "telecommunications"),
    (("criminal", "gun", "firearm", "bail", "sentence"), "federal", "criminal law"),
    (("military", "armed forces", "veteran"), "federal", "defence & veterans"),
    (("grocery", "food prices", "inflation"), "federal", "competition & economic policy"),
]


@dataclass(slots=True)
class JurisdictionGuess:
    level: str  # federal | provincial | municipal | mixed | unknown
    area: str | None = None


@dataclass(slots=True)
class MpBallotEvidence:
    """How the asker's own MP voted on a bill in the evidence set."""

    bill_number: str
    vote_number: str
    session: str
    chamber: str
    occurred_on: date
    description_en: str
    # advanced | blocked | None (from ballot x motion direction)
    effect: str | None
    ballot: str


@dataclass(slots=True)
class AskResponse:
    question: str
    answer_sentence: str | None
    answer_detail: str | None
    jurisdiction_level: str
    jurisdiction_note: str | None
    responsible_ministry: str | None
    evidence: list[SearchResult] = field(default_factory=list)
    cited_indexes: list[int] = field(default_factory=list)
    generated: bool = False  # False => degraded (search-only) mode
    my_mp_name: str | None = None
    my_mp_slug: str | None = None
    mp_ballots: list[MpBallotEvidence] = field(default_factory=list)


def _mp_ballots_for_evidence(
    db: Session, mp_person_id: int, evidence: list[SearchResult]
) -> list[MpBallotEvidence]:
    """The asker's MP's actual ballots on the bills we just retrieved."""
    from app.api.behavior import _ballot_effect
    from app.models import Ballot, Vote

    bill_ids = [item.entity_id for item in evidence if item.entity_type == "bill"]
    if not bill_ids:
        return []
    ballots = db.scalars(
        select(Ballot)
        .join(Vote, Ballot.vote_id == Vote.id)
        .where(Ballot.person_id == mp_person_id, Vote.bill_id.in_(bill_ids))
        .options(
            selectinload(Ballot.vote).selectinload(Vote.session),
            selectinload(Ballot.vote).selectinload(Vote.chamber),
            selectinload(Ballot.vote).selectinload(Vote.bill),
        )
        .order_by(Vote.occurred_on.desc())
        .limit(10)
    ).all()
    return [
        MpBallotEvidence(
            bill_number=b.vote.bill.number if b.vote.bill else "",
            vote_number=b.vote.number,
            session=b.vote.session.label,
            chamber=b.vote.chamber.slug,
            occurred_on=b.vote.occurred_on,
            description_en=b.vote.plain_meaning_en or b.vote.description_en,
            effect=_ballot_effect(b.ballot, b.vote.yea_effect),
            ballot=b.ballot,
        )
        for b in ballots
    ]


def heuristic_jurisdiction(question: str) -> JurisdictionGuess:
    q = f" {question.lower()} "
    for keywords, level, area in JURISDICTION_HINTS:
        if any(kw in q for kw in keywords):
            return JurisdictionGuess(level=level, area=area)
    return JurisdictionGuess(level="unknown")


ASK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer_sentence": {
            "type": "string",
            "description": "One plain sentence answering the question, naming who is responsible.",
        },
        "answer_detail": {
            "type": "string",
            "description": "2-3 short paragraphs: what is happening federally, citing evidence as [1], [2].",
        },
        "jurisdiction_level": {
            "type": "string",
            "enum": ["federal", "provincial", "municipal", "mixed"],
        },
        "jurisdiction_note": {
            "type": "string",
            "description": "One sentence: why that level of government owns this.",
        },
        "responsible_ministry": {
            "type": "string",
            "description": "The federal ministry/department most responsible, if any (e.g. 'Finance Canada').",
        },
        "cited_indexes": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "1-based indexes into the evidence list actually cited.",
        },
    },
    "required": ["answer_sentence", "answer_detail", "jurisdiction_level", "jurisdiction_note", "cited_indexes"],
}


def _evidence_block(evidence: list[SearchResult]) -> str:
    kinds = {"bill": "Bill", "vote": "Vote", "petition": "Petition (open for public signature)"}
    lines = []
    for i, item in enumerate(evidence, start=1):
        kind = kinds.get(item.entity_type, item.entity_type)
        outcome = f" (outcome: {item.outcome.replace('_', ' ')})" if item.outcome else ""
        lines.append(f"[{i}] {kind}: {item.title}{outcome} — {item.snippet}")
    return "\n".join(lines) or "(no matching federal evidence found)"


def _answer_gate_text(data: dict[str, Any]) -> str:
    return " ".join(filter(None, [data.get("answer_sentence"), data.get("jurisdiction_note")]))


async def ask(db: Session, question: str, *, mp_person_id: int | None = None) -> AskResponse:
    evidence = await hybrid_search(db, question, limit=10)
    guess = heuristic_jurisdiction(question)

    my_mp_name: str | None = None
    my_mp_slug: str | None = None
    mp_ballots: list[MpBallotEvidence] = []
    if mp_person_id is not None:
        from app.models import Person

        mp = db.get(Person, mp_person_id)
        if mp is not None:
            my_mp_name = mp.full_name
            my_mp_slug = mp.slug
            mp_ballots = _mp_ballots_for_evidence(db, mp_person_id, evidence)

    client = LLMClient()
    if not client.is_configured():
        return AskResponse(
            question=question,
            answer_sentence=None,
            answer_detail=None,
            jurisdiction_level=guess.level,
            jurisdiction_note=(f"This looks like a {guess.level} matter ({guess.area})." if guess.area else None),
            responsible_ministry=None,
            evidence=evidence,
            generated=False,
            my_mp_name=my_mp_name,
            my_mp_slug=my_mp_slug,
            mp_ballots=mp_ballots,
        )

    ensure_budget(db)
    hint = (
        f"A keyword heuristic suggests this may be {guess.level}"
        + (f" ({guess.area})" if guess.area else "")
        + ", but use your own judgment."
        if guess.level != "unknown"
        else ""
    )
    prompt = (
        f"A Canadian asks: \"{question}\"\n\n"
        "Decide which level of government is mainly responsible (federal, "
        "provincial, municipal, or mixed) and answer their question. "
        f"{hint}\n\n"
        "Federal evidence you may cite (bills and Commons votes from our "
        "database):\n"
        f"{_evidence_block(evidence)}\n\n"
        "Rules: answer_sentence first and plain. Cite evidence as [n] inside "
        "answer_detail, and list the numbers you used in cited_indexes. Never "
        "cite anything not in the list. If responsibility is provincial or "
        "municipal, say so directly and still mention any relevant federal "
        "activity from the evidence."
    )
    result = await asyncio.to_thread(
        client.structured_response,
        prompt=prompt,
        schema=ASK_SCHEMA,
        system=NEUTRAL_SYSTEM,
        max_tokens=1500,
    )
    record_usage(db, result, job_name="ask")

    gate_text = _answer_gate_text(result.data)
    if gate_text and not meets_gate(gate_text):
        ensure_budget(db)
        retry = await asyncio.to_thread(
            client.structured_response,
            prompt=prompt + "\n\n" + SIMPLIFY_INSTRUCTION.format(grade=reading_grade(gate_text)),
            schema=ASK_SCHEMA,
            system=NEUTRAL_SYSTEM,
            max_tokens=1500,
        )
        record_usage(db, retry, job_name="ask_retry")
        if reading_grade(_answer_gate_text(retry.data)) <= reading_grade(gate_text):
            result = retry

    db.commit()

    data = result.data
    valid_indexes = [i for i in (data.get("cited_indexes") or []) if isinstance(i, int) and 1 <= i <= len(evidence)]
    return AskResponse(
        question=question,
        answer_sentence=data.get("answer_sentence"),
        answer_detail=data.get("answer_detail"),
        jurisdiction_level=data.get("jurisdiction_level") or guess.level,
        jurisdiction_note=data.get("jurisdiction_note"),
        responsible_ministry=data.get("responsible_ministry") or None,
        evidence=evidence,
        cited_indexes=valid_indexes,
        generated=True,
        my_mp_name=my_mp_name,
        my_mp_slug=my_mp_slug,
        mp_ballots=mp_ballots,
    )
