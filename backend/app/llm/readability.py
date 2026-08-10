"""Readability gate: enforced grade 6-8 plain language.

Every user-facing AI summary is scored (Flesch-Kincaid). Text above the
gate gets regenerated with a simplification pass before it can publish.
"""
from __future__ import annotations

import textstat

# Target ceiling for plain-language output (allows brief grade-8 sentences).
TARGET_GRADE = 8.5
# Absolute ceiling: above this after retries, the analysis is blocked.
HARD_CEILING = 11.0


def reading_grade(text: str) -> float:
    if not text or not text.strip():
        return 0.0
    return float(textstat.flesch_kincaid_grade(text))


def meets_gate(text: str) -> bool:
    return reading_grade(text) <= TARGET_GRADE


def within_hard_ceiling(text: str) -> bool:
    return reading_grade(text) <= HARD_CEILING


SIMPLIFY_INSTRUCTION = (
    "Your previous answer was too complex (reading grade {grade:.1f}; the target is grade 8 or below). "
    "Rewrite it in shorter sentences with everyday words a 12-year-old knows. "
    "Do not add new facts. Keep the same structure."
)
