from __future__ import annotations


def frame_bill(summary: str, debate_context: str) -> dict:
    return {
        "analysis_type": "framing",
        "status": "pending",
        "payload": {
            "supporter_position": None,
            "opponent_position": None,
            "debate_excerpt_preview": debate_context[:500],
        },
    }
