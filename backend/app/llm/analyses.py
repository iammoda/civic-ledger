"""Claude analysis jobs: bill summaries, vote direction, topic tagging.

Design rules:
- Readability gate: user-facing text must hit grade <= 8.5 (one retry,
  hard ceiling 11 or the analysis is blocked, never silently published).
- Budget gate: every call checks the monthly cap first.
- Cache forever: a published AnalysisResult is never regenerated unless
  force=True (the lazy-analysis engine's contract).
- Heuristics before models: vote direction is resolved deterministically
  where possible; the LLM only sees the ambiguous minority.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.billtext import fetch_bill_text
from app.llm.base import LLMClient, StructuredResult
from app.llm.budget import ensure_budget, record_usage
from app.llm.readability import (
    HARD_CEILING,
    SIMPLIFY_INSTRUCTION,
    meets_gate,
    reading_grade,
    within_hard_ceiling,
)
from app.models import AnalysisResult, Bill, EntityTopic, Topic, Vote

NEUTRAL_SYSTEM = (
    "You are a rigorously neutral, non-partisan civic analyst for a Canadian "
    "public accountability platform. Facts only; no praise or blame; no loaded "
    "words. Write for a 12-year-old (reading grade 8 or below): short sentences, "
    "everyday words. Never invent facts not present in the source material."
)


# ---------------------------------------------------------------------------
# Bill plain-language summary (the layered depth content)
# ---------------------------------------------------------------------------

BILL_SUMMARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "one_sentence": {
            "type": "string",
            "description": "One plain sentence: what this bill would do.",
        },
        "what_it_does": {
            "type": "array",
            "items": {"type": "string"},
            "description": "2-4 short bullets: the main things the bill does.",
        },
        "who_it_affects": {
            "type": "array",
            "items": {"type": "string"},
            "description": "2-4 short bullets: groups of people affected and how.",
        },
        "what_changes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "2-4 short bullets: what changes for an ordinary person.",
        },
        "detailed_summary": {
            "type": "string",
            "description": "A fuller plain-language summary, 2-4 short paragraphs.",
        },
        "confidence": {
            "type": "number",
            "description": "0-1: how confident you are, given the source material.",
        },
    },
    "required": [
        "one_sentence",
        "what_it_does",
        "who_it_affects",
        "what_changes",
        "detailed_summary",
        "confidence",
    ],
}


def _summary_text_for_gate(payload: dict[str, Any]) -> str:
    parts = [payload.get("one_sentence", "")]
    for key in ("what_it_does", "who_it_affects", "what_changes"):
        parts.extend(payload.get(key) or [])
    return " ".join(p for p in parts if p)


def _bill_prompt(bill: Bill, bill_text: str | None) -> str:
    lines = [
        f"Bill {bill.number} ({bill.session.label if bill.session else ''}) — {bill.title_en}",
    ]
    if bill.short_title_en:
        lines.append(f"Short title: {bill.short_title_en}")
    lines.append(f"Type: {'private member' if bill.bill_type == 'private_member' else 'government'} bill")
    if bill.status_en:
        lines.append(f"Current status: {bill.status_en}")
    if bill.outcome and bill.outcome != "pending":
        lines.append(f"Outcome: {bill.outcome.replace('_', ' ')}")
    if bill_text:
        lines.append("\n--- BILL TEXT (may be truncated) ---\n")
        lines.append(bill_text)
    else:
        lines.append(
            "\nNo bill text is available. Summarize ONLY what the title and status "
            "support, and say clearly that details are limited."
        )
    lines.append(
        "\nSummarize this bill for an ordinary person. Neutral facts only. "
        "Reading grade 8 or below."
    )
    return "\n".join(lines)


async def analyze_bill(db: Session, bill_id: int, *, force: bool = False) -> AnalysisResult | None:
    """Generate (or return cached) plain-language summary for a bill."""
    bill = db.get(Bill, bill_id)
    if bill is None:
        return None

    existing = db.scalar(
        select(AnalysisResult).where(
            AnalysisResult.bill_id == bill_id,
            AnalysisResult.analysis_type == "plain_summary",
            AnalysisResult.language == "en",
        )
    )
    if existing is not None and existing.status == "published" and not force:
        return existing  # Cache forever.

    client = LLMClient()
    if not client.is_configured():
        return None  # Stays a Data Gap; never fabricate.

    ensure_budget(db)

    bill_text = None
    if bill.text_url:
        bill_text = await fetch_bill_text(db, bill_id=bill.id, text_url=bill.text_url)

    prompt = _bill_prompt(bill, bill_text)
    result = await asyncio.to_thread(
        client.structured_response,
        prompt=prompt,
        schema=BILL_SUMMARY_SCHEMA,
        system=NEUTRAL_SYSTEM,
    )
    record_usage(db, result, job_name="bill_plain_summary", entity_type="bill", entity_id=bill.id)

    # Readability gate: one simplification retry, then hard ceiling.
    gate_text = _summary_text_for_gate(result.data)
    if not meets_gate(gate_text):
        ensure_budget(db)
        retry_prompt = (
            prompt
            + "\n\n"
            + SIMPLIFY_INSTRUCTION.format(grade=reading_grade(gate_text))
        )
        retry = await asyncio.to_thread(
            client.structured_response,
            prompt=retry_prompt,
            schema=BILL_SUMMARY_SCHEMA,
            system=NEUTRAL_SYSTEM,
        )
        record_usage(db, retry, job_name="bill_plain_summary_retry", entity_type="bill", entity_id=bill.id)
        if reading_grade(_summary_text_for_gate(retry.data)) <= reading_grade(gate_text):
            result = retry
            gate_text = _summary_text_for_gate(result.data)

    if existing is None:
        existing = AnalysisResult(bill_id=bill.id, analysis_type="plain_summary", language="en")
        db.add(existing)

    grade = reading_grade(gate_text)
    existing.model_name = result.model
    existing.confidence_score = float(result.data.get("confidence") or 0.0)
    existing.payload = {**result.data, "reading_grade": grade, "had_bill_text": bool(bill_text)}
    existing.citations = _bill_citations(bill)
    if within_hard_ceiling(gate_text):
        existing.status = "published"
        existing.blocked_reason = None
    else:
        existing.status = "blocked"
        existing.blocked_reason = (
            f"Readability gate failed after retry (grade {grade:.1f} > {HARD_CEILING})."
        )
    db.commit()
    return existing


def _bill_citations(bill: Bill) -> list[dict[str, str]]:
    citations = []
    if bill.legisinfo_url:
        citations.append({"label": "LEGISinfo (official bill record)", "url": bill.legisinfo_url})
    if bill.text_url:
        citations.append({"label": "Full bill text (parl.ca)", "url": bill.text_url})
    return citations


# ---------------------------------------------------------------------------
# Vote direction normalization ("voted to advance" / "voted to block")
# ---------------------------------------------------------------------------

VOTE_MEANING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "yea_effect": {
            "type": "string",
            "enum": ["advance", "block", "other"],
            "description": (
                "What a Yes vote did to the underlying bill/matter: advance it, "
                "block/kill/delay it, or 'other' when neither applies."
            ),
        },
        "plain_meaning": {
            "type": "string",
            "description": "One sentence, grade 8: what this vote actually decided.",
        },
    },
    "required": ["yea_effect", "plain_meaning"],
}

# Deterministic patterns resolve the common cases for free.
_ADVANCE_PATTERNS = [
    r"\b(2nd|3rd|second|third) reading and adoption\b",
    r"\bbe now read a (first|second|third) time\b",
    r"\bconcurrence at report stage\b",
    r"\bpassage,? at third reading\b",
    r"\btime allocation\b",
    r"\bclosure\b",
]
_BLOCK_PATTERNS = [
    r"\bbe not now read\b",
    r"\bsix months hence\b",  # hoist amendment
    r"\breasoned amendment\b",
    r"\bthat the motion be amended by deleting all the words\b",
]


def heuristic_vote_direction(description: str) -> str | None:
    desc = description.lower()
    for pattern in _BLOCK_PATTERNS:
        if re.search(pattern, desc):
            return "block"
    for pattern in _ADVANCE_PATTERNS:
        if re.search(pattern, desc):
            return "advance"
    return None


def _heuristic_plain_meaning(vote: Vote, effect: str) -> str:
    outcome = "passed" if (vote.result or "").lower() == "passed" else "did not pass"
    if effect == "advance":
        return (
            f"A Yes vote moved this forward. The motion {outcome}, "
            f"{vote.yea_total} to {vote.nay_total}."
        )
    return (
        f"A Yes vote blocked this from moving forward. The motion {outcome}, "
        f"{vote.yea_total} to {vote.nay_total}."
    )


async def normalize_vote(db: Session, vote_id: int, *, force: bool = False) -> Vote | None:
    """Fill Vote.yea_effect + plain_meaning_en. Heuristics first, LLM fallback."""
    vote = db.get(Vote, vote_id)
    if vote is None:
        return None
    if vote.yea_effect and not force:
        return vote

    effect = heuristic_vote_direction(vote.description_en)
    if effect is not None:
        vote.yea_effect = effect
        vote.plain_meaning_en = _heuristic_plain_meaning(vote, effect)
        db.commit()
        return vote

    client = LLMClient(fast=True)
    if not client.is_configured():
        return vote  # Leave unset; UI shows raw description.

    ensure_budget(db)
    bill_context = ""
    if vote.bill_id:
        bill = db.get(Bill, vote.bill_id)
        if bill is not None:
            bill_context = f"\nRelated bill: {bill.number} — {bill.title_en}"

    prompt = (
        "This is a recorded division in the Canadian House of Commons. "
        "Procedural motions can invert meaning (a Yes on a hoist or reasoned "
        "amendment BLOCKS the bill). Decide what a Yes vote did to the "
        "underlying matter, and write one plain sentence (grade 8) saying what "
        f"the vote decided.\n\nMotion: {vote.description_en}\n"
        f"Result: {vote.result}; {vote.yea_total} Yes, {vote.nay_total} No."
        f"{bill_context}"
    )
    result = await asyncio.to_thread(
        client.structured_response,
        prompt=prompt,
        schema=VOTE_MEANING_SCHEMA,
        system=NEUTRAL_SYSTEM,
        max_tokens=512,
    )
    record_usage(db, result, job_name="vote_direction", entity_type="vote", entity_id=vote.id)

    vote.yea_effect = result.data.get("yea_effect") or "other"
    meaning = result.data.get("plain_meaning") or ""
    if meaning and within_hard_ceiling(meaning):
        vote.plain_meaning_en = meaning
    db.commit()
    return vote


# ---------------------------------------------------------------------------
# Topic tagging (alias match free pass + Haiku)
# ---------------------------------------------------------------------------

TOPIC_TAG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["slug", "confidence"],
            },
            "description": "Topics that clearly apply (max 4).",
        }
    },
    "required": ["topics"],
}


def _alias_match_topics(db: Session, text: str) -> list[tuple[Topic, float]]:
    text_lower = text.lower()
    matches = []
    for topic in db.scalars(select(Topic)).all():
        terms = [topic.name_en.lower()]
        if topic.aliases_en:
            terms.extend(a.strip().lower() for a in topic.aliases_en.split(","))
        if any(term and term in text_lower for term in terms):
            matches.append((topic, 0.6))
    return matches


def _upsert_entity_topic(db: Session, topic: Topic, entity_type: str, entity_id: int, confidence: float, source: str) -> None:
    existing = db.scalar(
        select(EntityTopic).where(
            EntityTopic.topic_id == topic.id,
            EntityTopic.entity_type == entity_type,
            EntityTopic.entity_id == entity_id,
        )
    )
    if existing is None:
        existing = EntityTopic(topic_id=topic.id, entity_type=entity_type, entity_id=entity_id)
        db.add(existing)
    # LLM tags overwrite alias tags; alias tags never downgrade LLM ones.
    if source == "llm" or existing.source != "llm":
        existing.confidence = confidence
        existing.source = source
    db.flush()


async def tag_bill_topics(db: Session, bill_id: int, *, force: bool = False) -> int:
    """Tag a bill against the curated taxonomy. Alias pass is free; Haiku
    refines when configured."""
    bill = db.get(Bill, bill_id)
    if bill is None:
        return 0

    if not force:
        already = db.scalar(
            select(EntityTopic.id)
            .where(EntityTopic.entity_type == "bill", EntityTopic.entity_id == bill_id, EntityTopic.source == "llm")
            .limit(1)
        )
        if already is not None:
            return 0

    text = " ".join(filter(None, [bill.number, bill.title_en, bill.short_title_en, bill.status_en]))

    count = 0
    for topic, confidence in _alias_match_topics(db, text):
        _upsert_entity_topic(db, topic, "bill", bill.id, confidence, "alias")
        count += 1

    client = LLMClient(fast=True)
    if client.is_configured():
        ensure_budget(db)
        taxonomy = db.scalars(select(Topic)).all()
        taxonomy_desc = "\n".join(f"- {t.slug}: {t.name_en} ({t.aliases_en or ''})" for t in taxonomy)
        prompt = (
            "Tag this Canadian federal bill with the topics that clearly apply "
            "(max 4). Use only slugs from the taxonomy.\n\n"
            f"Bill: {text}\n\nTaxonomy:\n{taxonomy_desc}"
        )
        result = await asyncio.to_thread(
            client.structured_response,
            prompt=prompt,
            schema=TOPIC_TAG_SCHEMA,
            system=NEUTRAL_SYSTEM,
            max_tokens=512,
        )
        record_usage(db, result, job_name="bill_topic_tagging", entity_type="bill", entity_id=bill.id)
        valid = {t.slug: t for t in taxonomy}
        for item in result.data.get("topics") or []:
            topic = valid.get(item.get("slug"))
            if topic is None:
                continue
            _upsert_entity_topic(db, topic, "bill", bill.id, float(item.get("confidence") or 0.5), "llm")
            count += 1

    db.commit()
    return count
