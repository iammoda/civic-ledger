"""One-line LLM descriptions of organizations that lobby parliamentarians.

Answers "what even is Jack.org?" right where the lobbying record appears.
Rules match the other analysis jobs: budget-gated, cached forever,
descriptive only — the model describes what the org IS, never what its
lobbying "means".
"""
from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.base import LLMClient
from app.llm.budget import ensure_budget, record_usage
from app.models import LobbyOrgProfile

ORG_PROFILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "description": {
            "type": "string",
            "description": (
                "One factual sentence (max ~25 words) saying what this organization is: "
                "sector, what it does, who it represents. No opinions."
            ),
        },
        "known": {
            "type": "boolean",
            "description": "false if you don't reliably know this organization — never guess.",
        },
    },
    "required": ["description", "known"],
}

_SYSTEM = (
    "You identify Canadian organizations neutrally for a civic transparency site. "
    "One plain sentence: what the organization is (charity, industry association, "
    "company, union...), what it does, who it represents. Grade 8 reading level. "
    "If you are not confident you know the organization, set known=false. Never guess."
)


async def profile_org(db: Session, org_name: str) -> LobbyOrgProfile | None:
    """Generate (or fetch cached) a one-line description for a lobbying org."""
    name = (org_name or "").strip()
    if not name:
        return None

    existing = db.scalar(select(LobbyOrgProfile).where(LobbyOrgProfile.org_name == name))
    if existing is not None and existing.status != "pending":
        return existing  # Cache forever.

    client = LLMClient(fast=True)
    if not client.is_configured():
        return existing

    ensure_budget(db)
    result = await asyncio.to_thread(
        client.structured_response,
        prompt=(
            "Organization from the Canadian federal Registry of Lobbyists "
            f"(a client that lobbied MPs): {name!r}. What is this organization?"
        ),
        schema=ORG_PROFILE_SCHEMA,
        system=_SYSTEM,
        max_tokens=256,
    )
    record_usage(db, result, job_name="lobby_org_profile", entity_type="org", entity_id=None)

    profile = existing or LobbyOrgProfile(org_name=name)
    known = bool(result.data.get("known"))
    description = (result.data.get("description") or "").strip()
    if known and description:
        profile.description_en = description
        profile.status = "published"
    else:
        # Honest gap: an unknown org stays blank rather than hallucinated.
        profile.description_en = None
        profile.status = "blocked"
    profile.model_name = result.model
    db.add(profile)
    db.commit()
    return profile


def published_profiles(db: Session, org_names: list[str]) -> dict[str, str]:
    """Cached descriptions for a set of org names (published only)."""
    names = [n for n in {(n or "").strip() for n in org_names} if n]
    if not names:
        return {}
    rows = db.scalars(
        select(LobbyOrgProfile).where(
            LobbyOrgProfile.org_name.in_(names),
            LobbyOrgProfile.status == "published",
        )
    ).all()
    return {p.org_name: p.description_en or "" for p in rows if p.description_en}


def unprofiled(db: Session, org_names: list[str]) -> list[str]:
    """Org names with no profile row yet (candidates for the lazy job)."""
    names = [n for n in {(n or "").strip() for n in org_names} if n]
    if not names:
        return []
    have = set(
        db.scalars(select(LobbyOrgProfile.org_name).where(LobbyOrgProfile.org_name.in_(names))).all()
    )
    return [n for n in names if n not in have]
