from __future__ import annotations

from typing import Any

from openai import OpenAI

from app.core.config import get_settings


settings = get_settings()


class LLMClient:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self.model = settings.openai_model

    def is_configured(self) -> bool:
        return self.client is not None

    def structured_response(self, *, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if self.client is None:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "analysis",
                    "schema": schema,
                }
            },
        )
        output_text = response.output_text
        return {"raw_text": output_text}
