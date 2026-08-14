"""LLM clients.

- ``LLMClient``: Claude (Anthropic) for all analysis/extraction. Structured
  output is enforced via tool-use with a JSON schema, so responses parse or
  fail loudly — never silently degrade.
- ``EmbeddingClient``: OpenAI embeddings (Anthropic has no embeddings API).

Both are lazily configured: without API keys they report unconfigured and
callers must treat analysis as a Data Gap, never fabricate.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic
from openai import OpenAI

from app.core.config import get_settings


settings = get_settings()


@dataclass(slots=True)
class StructuredResult:
    """Parsed structured output plus token usage for the cost ledger."""

    data: dict[str, Any]
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMClient:
    def __init__(self, *, fast: bool = False) -> None:
        self.client = Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None
        self.model = settings.anthropic_fast_model if fast else settings.anthropic_model

    def is_configured(self) -> bool:
        return self.client is not None

    def structured_response(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> StructuredResult:
        """Return schema-conforming JSON by forcing a tool call."""
        if self.client is None:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system or "You are a rigorously neutral, non-partisan civic data analyst.",
            messages=[{"role": "user", "content": prompt}],
            tools=[
                {
                    "name": "emit_analysis",
                    "description": "Emit the structured analysis result.",
                    "input_schema": schema,
                }
            ],
            tool_choice={"type": "tool", "name": "emit_analysis"},
        )
        usage = getattr(response, "usage", None)
        for block in response.content:
            if block.type == "tool_use":
                return StructuredResult(
                    data=dict(block.input),
                    model=self.model,
                    input_tokens=getattr(usage, "input_tokens", 0) or 0,
                    output_tokens=getattr(usage, "output_tokens", 0) or 0,
                )
        raise RuntimeError(f"Model returned no tool_use block: {json.dumps([b.type for b in response.content])}")


class EmbeddingClient:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self.model = settings.embedding_model

    def is_configured(self) -> bool:
        return self.client is not None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.client is None:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        response = self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]
