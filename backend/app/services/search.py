"""Hybrid search: keyword (Postgres FTS, LIKE fallback) + vector, RRF-fused.

Alias expansion bridges colloquial language ("carbon tax") to legislative
language ("fuel charge") using the curated topic taxonomy.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, or_, select, text as sql_text
from sqlalchemy.orm import Session, selectinload

from app.models import Bill, Embedding, Petition, Topic, Vote

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
    """Append topic names/aliases matched by the query text. Matches both
    aliases ('carbon tax') and significant words of topic names
    ('environment' in 'Climate & Environment')."""
    query_lower = query.lower()
    extras: list[str] = []
    for topic in db.scalars(select(Topic)).all():
        aliases = [a.strip() for a in (topic.aliases_en or "").split(",") if a.strip()]
        name_words = [w for w in topic.name_en.lower().replace("&", " ").split() if len(w) >= 5]
        hit = any(alias.lower() in query_lower for alias in aliases) or any(
            word in query_lower for word in name_words
        )
        if hit and topic.name_en.lower() not in query_lower:
            extras.append(topic.name_en)
            extras.extend(aliases)
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


def _petition_result(petition: Petition) -> SearchResult:
    snippet_bits = []
    if petition.state == "open":
        snippet_bits.append(
            f"Open for signature{f' until {petition.closes_at}' if petition.closes_at else ''}"
        )
        snippet_bits.append(f"{petition.signature_count:,} signatures")
    else:
        snippet_bits.append(petition.status_en or "Closed")
    return SearchResult(
        entity_type="petition",
        entity_id=petition.id,
        title=f"Petition {petition.number} — {petition.title_en}",
        snippet=" · ".join(snippet_bits),
        # External official page (also where people sign).
        url_path=petition.source_url,
    )


_FTS_STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "have", "what", "who",
    "why", "how", "can", "cant", "cannot", "about", "will", "are", "was", "not",
    "anymore", "responsible", "afford", "should", "would", "could", "does",
}


def _fts_or_query(db: Session, query: str):
    """OR-of-significant-words tsquery: natural questions ('why is rent so
    high') must not require every word to appear (plainto_tsquery ANDs)."""
    import re

    tokens = [
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", query.lower())
        if token not in _FTS_STOPWORDS
    ]
    if not tokens:
        return None
    return func.to_tsquery("english", " | ".join(dict.fromkeys(tokens[:12])))


def keyword_search(db: Session, query: str, *, limit: int = 20) -> list[SearchResult]:
    results: list[SearchResult] = []

    if _is_postgres(db):
        ts_query = _fts_or_query(db, query)
        if ts_query is None:
            return []
        # bills.search_tsv is a weighted generated column (number/short title
        # rank A, title/official summary B, full text D) — content matches
        # work even when titles don't ("protecting the environment").
        from sqlalchemy import text as sql_text_expr

        bill_doc = sql_text_expr("bills.search_tsv")
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
        petition_doc = func.to_tsvector(
            "english",
            Petition.title_en
            + " "
            + func.coalesce(Petition.keywords_en, "")
            + " "
            + func.coalesce(Petition.text_en, ""),
        )
        petitions = db.scalars(
            select(Petition)
            .where(petition_doc.op("@@")(ts_query))
            .order_by(Petition.state.asc(), func.ts_rank(petition_doc, ts_query).desc())
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
        petitions = db.scalars(
            select(Petition)
            .where(or_(*clauses(Petition.title_en, Petition.keywords_en, Petition.text_en)))
            .limit(limit)
        ).all()

    results.extend(_bill_result(b) for b in bills)
    results.extend(_vote_result(v) for v in votes)
    results.extend(_petition_result(p) for p in petitions)
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
        elif entity_type == "petition":
            petition = db.get(Petition, entity_id)
            if petition is not None:
                results.append(_petition_result(petition))
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
    # Original-query matches rank ahead of alias-expanded ones: expansion
    # recalls related content but must not drown direct hits.
    keyword_lists = [keyword_search(db, query, limit=limit)]
    if expanded != query:
        keyword_lists.append(keyword_search(db, expanded, limit=limit))

    vector_results: list[SearchResult] = []
    if _is_postgres(db):
        query_vector = await embed_query(expanded)
        if query_vector is not None:
            vector_results = vector_search(db, query_vector, limit=limit)

    if vector_results:
        keyword_lists.append(vector_results)
    return rrf_fuse(keyword_lists, limit=limit)
