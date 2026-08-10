"""Hybrid search: keyword (Postgres FTS, LIKE fallback) + vector, RRF-fused.

Alias expansion bridges colloquial language ("carbon tax") to legislative
language ("fuel charge") using the curated topic taxonomy.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, or_, select, text as sql_text
from sqlalchemy.orm import Session, selectinload

from app.models import Bill, Embedding, Topic, Vote

RRF_K = 60


@dataclass(slots=True)
class SearchResult:
    entity_type: str  # "bill" | "vote"
    entity_id: int
    title: str
    snippet: str
    url_path: str
    score: float = 0.0
    outcome: str | None = None


def _is_postgres(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def expand_query(db: Session, query: str) -> str:
    """Append topic names/aliases matched by the query text."""
    query_lower = query.lower()
    extras: list[str] = []
    for topic in db.scalars(select(Topic)).all():
        aliases = [a.strip() for a in (topic.aliases_en or "").split(",") if a.strip()]
        for alias in aliases:
            if alias.lower() in query_lower and topic.name_en.lower() not in query_lower:
                extras.append(topic.name_en)
                extras.extend(a for a in aliases if a.lower() != alias.lower())
                break
    if not extras:
        return query
    return f"{query} {' '.join(dict.fromkeys(extras))}"


def _bill_result(bill: Bill) -> SearchResult:
    return SearchResult(
        entity_type="bill",
        entity_id=bill.id,
        title=f"{bill.number} — {bill.short_title_en or bill.title_en}",
        snippet=bill.status_en or bill.title_en,
        url_path=f"/bills/{bill.session.label}/{bill.number}",
        outcome=bill.outcome,
    )


def _vote_result(vote: Vote) -> SearchResult:
    return SearchResult(
        entity_type="vote",
        entity_id=vote.id,
        title=f"Vote {vote.number} ({vote.session.label})",
        snippet=vote.plain_meaning_en or vote.description_en,
        url_path=f"/votes/{vote.chamber.slug}/{vote.session.label}/{vote.number}",
    )


def keyword_search(db: Session, query: str, *, limit: int = 20) -> list[SearchResult]:
    results: list[SearchResult] = []

    if _is_postgres(db):
        ts_query = func.plainto_tsquery("english", query)
        bill_doc = func.to_tsvector(
            "english",
            Bill.number
            + " "
            + Bill.title_en
            + " "
            + func.coalesce(Bill.short_title_en, "")
            + " "
            + func.coalesce(Bill.status_en, ""),
        )
        bills = db.scalars(
            select(Bill)
            .options(selectinload(Bill.session), selectinload(Bill.chamber))
            .where(bill_doc.op("@@")(ts_query))
            .order_by(func.ts_rank(bill_doc, ts_query).desc())
            .limit(limit)
        ).all()
        vote_doc = func.to_tsvector("english", Vote.description_en)
        votes = db.scalars(
            select(Vote)
            .options(selectinload(Vote.session), selectinload(Vote.chamber))
            .where(vote_doc.op("@@")(ts_query))
            .order_by(func.ts_rank(vote_doc, ts_query).desc())
            .limit(limit)
        ).all()
    else:
        # Dev/test fallback: per-word LIKE across the same fields.
        words = [w for w in query.split() if len(w) >= 3][:8]
        if not words:
            return []

        def clauses(*columns):
            return [
                or_(*[func.lower(func.coalesce(col, "")).contains(word.lower()) for col in columns])
                for word in words
            ]

        bills = db.scalars(
            select(Bill)
            .options(selectinload(Bill.session), selectinload(Bill.chamber))
            .where(or_(*clauses(Bill.number, Bill.title_en, Bill.short_title_en, Bill.status_en)))
            .limit(limit)
        ).all()
        votes = db.scalars(
            select(Vote)
            .options(selectinload(Vote.session), selectinload(Vote.chamber))
            .where(or_(*clauses(Vote.description_en)))
            .limit(limit)
        ).all()

    results.extend(_bill_result(b) for b in bills)
    results.extend(_vote_result(v) for v in votes)
    return results


def vector_search(db: Session, query_vector: list[float], *, limit: int = 20) -> list[SearchResult]:
    """pgvector cosine search over embedded bills/votes. Postgres only."""
    if not _is_postgres(db):
        return []
    rows = db.execute(
        select(Embedding.entity_type, Embedding.entity_id)
        .order_by(Embedding.vector.cosine_distance(query_vector))
        .limit(limit)
    ).all()

    results: list[SearchResult] = []
    for entity_type, entity_id in rows:
        if entity_type == "bill":
            bill = db.scalar(
                select(Bill)
                .options(selectinload(Bill.session), selectinload(Bill.chamber))
                .where(Bill.id == entity_id)
            )
            if bill is not None:
                results.append(_bill_result(bill))
        elif entity_type == "vote":
            vote = db.scalar(
                select(Vote)
                .options(selectinload(Vote.session), selectinload(Vote.chamber))
                .where(Vote.id == entity_id)
            )
            if vote is not None:
                results.append(_vote_result(vote))
    return results


def rrf_fuse(result_lists: list[list[SearchResult]], *, k: int = RRF_K, limit: int = 20) -> list[SearchResult]:
    """Reciprocal rank fusion across ranked lists."""
    scores: dict[tuple[str, int], float] = {}
    first_seen: dict[tuple[str, int], SearchResult] = {}
    for results in result_lists:
        for rank, result in enumerate(results):
            key = (result.entity_type, result.entity_id)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            first_seen.setdefault(key, result)
    fused = sorted(first_seen.values(), key=lambda r: scores[(r.entity_type, r.entity_id)], reverse=True)
    for result in fused:
        result.score = round(scores[(result.entity_type, result.entity_id)], 6)
    return fused[:limit]


async def hybrid_search(db: Session, query: str, *, limit: int = 20) -> list[SearchResult]:
    from app.llm.embeddings import embed_query

    expanded = expand_query(db, query)
    keyword_results = keyword_search(db, expanded, limit=limit)

    vector_results: list[SearchResult] = []
    if _is_postgres(db):
        query_vector = await embed_query(expanded)
        if query_vector is not None:
            vector_results = vector_search(db, query_vector, limit=limit)

    if not vector_results:
        return rrf_fuse([keyword_results], limit=limit)
    return rrf_fuse([keyword_results, vector_results], limit=limit)
