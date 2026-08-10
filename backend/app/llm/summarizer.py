from __future__ import annotations

from app.llm.base import LLMClient


def summarize_bill(title: str, context: str) -> dict:
    client = LLMClient()
    return {
        "analysis_type": "bill_summary",
        "status": "pending" if not client.is_configured() else "queued",
        "payload": {"title": title, "context_preview": context[:500]},
    }
