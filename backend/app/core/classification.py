from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PartyDisagreementSignal:
    party_slug: str
    disagreement_pct: float


def classify_vote_type(
    *,
    description: str,
    yea_total: int,
    nay_total: int,
    disagreement_signals: list[PartyDisagreementSignal],
) -> str:
    description_lower = description.lower()

    if yea_total + nay_total == 0:
        return "voice"

    if "confidence" in description_lower or "budget" in description_lower or "speech from the throne" in description_lower:
        return "confidence"

    if disagreement_signals and all(signal.disagreement_pct == 0 for signal in disagreement_signals):
        return "whipped"

    if any(signal.disagreement_pct > 15 for signal in disagreement_signals):
        return "free"

    return "whipped"
