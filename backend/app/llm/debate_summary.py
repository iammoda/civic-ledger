from __future__ import annotations


def summarize_debate(text: str) -> dict:
    return {
        "analysis_type": "debate_summary",
        "status": "pending",
        "payload": {"summary_text": None, "text_preview": text[:500]},
    }
