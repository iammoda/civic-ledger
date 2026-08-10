from __future__ import annotations


DEFAULT_SECTORS = [
    "environment",
    "business/commerce",
    "healthcare",
    "labor/employment",
    "housing",
    "education",
    "civil liberties",
    "Indigenous affairs",
    "immigration",
    "national security",
]


def analyze_sector_impact(summary: str) -> dict:
    return {
        "analysis_type": "sector_impact",
        "status": "pending",
        "payload": {"sector_impacts": [], "summary_preview": summary[:500], "known_sectors": DEFAULT_SECTORS},
    }
