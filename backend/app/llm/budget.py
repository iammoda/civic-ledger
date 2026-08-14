"""LLM cost ledger and hard budget cap.

Every LLM call is recorded to llm_usage. Before any call, ensure_budget()
checks month-to-date spend against LLM_MONTHLY_BUDGET_USD and refuses to
proceed past it — a bug can't burn the budget.

Concurrency note: the check is check-then-act, so simultaneous requests can
overshoot the cap by at most (concurrent LLM calls x per-call cost — cents).
Inbound rate limiting bounds the concurrency; callers on hot public paths
should pass a small headroom_usd as extra margin.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm.base import StructuredResult
from app.models import LlmUsage

settings = get_settings()

# USD per million tokens: (input, output). Unknown models use a safe-high rate.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "text-embedding-3-small": (0.02, 0.0),
}
DEFAULT_PRICE = (10.0, 50.0)


class BudgetExceededError(RuntimeError):
    pass


def cost_for(model: str, input_tokens: int, output_tokens: int) -> float:
    inp, out = PRICES_PER_MTOK.get(model, DEFAULT_PRICE)
    return round((input_tokens * inp + output_tokens * out) / 1_000_000, 6)


def month_to_date_spend(db: Session) -> float:
    now = datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1)
    total = db.scalar(
        select(func.coalesce(func.sum(LlmUsage.cost_usd), 0.0)).where(
            LlmUsage.created_at >= month_start
        )
    )
    return float(total or 0.0)


def ensure_budget(db: Session, *, headroom_usd: float = 0.0) -> None:
    spend = month_to_date_spend(db)
    if spend + headroom_usd >= settings.llm_monthly_budget_usd:
        raise BudgetExceededError(
            f"Monthly LLM budget exhausted: ${spend:.2f} >= ${settings.llm_monthly_budget_usd:.2f}"
        )


def record_usage(
    db: Session,
    result: StructuredResult,
    *,
    job_name: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> LlmUsage:
    row = LlmUsage(
        model_name=result.model,
        job_name=job_name,
        entity_type=entity_type,
        entity_id=entity_id,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=cost_for(result.model, result.input_tokens, result.output_tokens),
    )
    db.add(row)
    db.flush()
    return row
