"""Embedding pipeline: bills/votes → pgvector, hash-skipped, cost-recorded.

Embeddings power hybrid search, Ask retrieval, and topic matching.
Content hashes mean re-runs only pay for changed text.
"""
from __future__ import annotations

import asyncio
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.base import EmbeddingClient, StructuredResult
from app.llm.budget import record_usage
from app.models import Bill, Chamber, Embedding, Meeting, Motion, Petition, Vote

EMBED_BATCH_SIZE = 96


def bill_embed_text(bill: Bill) -> str:
    parts = [
        bill.number,
        bill.title_en,
        bill.short_title_en or "",
        bill.status_en or "",
        (bill.outcome or "").replace("_", " "),
    ]
    return "\n".join(p for p in parts if p)


def vote_embed_text(vote: Vote) -> str:
    parts = [vote.description_en, vote.plain_meaning_en or "", vote.result or ""]
    return "\n".join(p for p in parts if p)


def petition_embed_text(petition: Petition) -> str:
    parts = [
        petition.number,
        petition.title_en,
        petition.keywords_en or "",
        (petition.text_en or "")[:4000],
    ]
    return "\n".join(p for p in parts if p)


def motion_embed_text(motion: Motion, city_name: str) -> str:
    """City name is embedded so 'potholes in Mississauga' retrieves the
    right council's decisions."""
    parts = [
        city_name,
        motion.meeting.body_name if motion.meeting else "",
        motion.item_title or "",
        (motion.text_en or "")[:3000],
        motion.result.replace("_", " "),
    ]
    return "\n".join(p for p in parts if p)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def embed_pending(db: Session, *, entity_type: str, limit: int = 500) -> int:
    """Embed entities whose content is new or changed. Returns count embedded."""
    client = EmbeddingClient()
    if not client.is_configured():
        return 0

    if entity_type == "bill":
        rows = db.scalars(select(Bill).order_by(Bill.id.desc()).limit(limit * 4)).all()
        texts = {row.id: bill_embed_text(row) for row in rows}
    elif entity_type == "vote":
        rows = db.scalars(select(Vote).order_by(Vote.id.desc()).limit(limit * 4)).all()
        texts = {row.id: vote_embed_text(row) for row in rows}
    elif entity_type == "petition":
        rows = db.scalars(select(Petition).order_by(Petition.id.desc()).limit(limit * 4)).all()
        texts = {row.id: petition_embed_text(row) for row in rows}
    elif entity_type == "motion":
        from sqlalchemy.orm import selectinload

        motion_rows = db.scalars(
            select(Motion)
            .options(selectinload(Motion.meeting).selectinload(Meeting.chamber).selectinload(Chamber.jurisdiction))
            .order_by(Motion.id.desc())
            .limit(limit * 4)
        ).all()
        texts = {
            row.id: motion_embed_text(
                row,
                row.meeting.chamber.jurisdiction.name_en if row.meeting and row.meeting.chamber else "",
            )
            for row in motion_rows
        }
    else:
        raise ValueError(f"Unsupported entity_type: {entity_type}")

    existing = {
        row.entity_id: row
        for row in db.scalars(select(Embedding).where(Embedding.entity_type == entity_type)).all()
    }

    pending: list[tuple[int, str, str]] = []
    for entity_id, text in texts.items():
        if not text:
            continue
        content_hash = _hash(text)
        current = existing.get(entity_id)
        if current is not None and current.content_hash == content_hash:
            continue
        pending.append((entity_id, text, content_hash))
        if len(pending) >= limit:
            break

    embedded = 0
    for start in range(0, len(pending), EMBED_BATCH_SIZE):
        batch = pending[start : start + EMBED_BATCH_SIZE]
        vectors = await asyncio.to_thread(client.embed, [text for _, text, _ in batch])
        total_chars = sum(len(text) for _, text, _ in batch)
        record_usage(
            db,
            StructuredResult(
                data={},
                model=client.model,
                # ~4 chars/token approximation for the ledger.
                input_tokens=total_chars // 4,
                output_tokens=0,
            ),
            job_name=f"embed_{entity_type}",
        )
        for (entity_id, _, content_hash), vector in zip(batch, vectors):
            row = existing.get(entity_id)
            if row is None:
                row = Embedding(entity_type=entity_type, entity_id=entity_id, content_hash="", model_name=client.model, vector=vector)
                db.add(row)
                existing[entity_id] = row
            row.content_hash = content_hash
            row.model_name = client.model
            row.vector = vector
            embedded += 1
        db.commit()
    return embedded


async def embed_query(text: str) -> list[float] | None:
    client = EmbeddingClient()
    if not client.is_configured():
        return None
    vectors = await asyncio.to_thread(client.embed, [text])
    return vectors[0]
