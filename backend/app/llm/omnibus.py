from __future__ import annotations


def decompose_bill(bill_text: str) -> dict:
    return {
        "analysis_type": "omnibus",
        "status": "pending",
        "payload": {"components": [], "text_preview": bill_text[:500]},
    }
