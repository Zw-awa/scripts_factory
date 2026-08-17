from __future__ import annotations

import json
import os

from .base import Provider, SessionRequest, SessionResult


class OpenAIResponsesProvider(Provider):
    name = "openai"

    async def healthcheck(self) -> tuple[bool, str]:
        return (bool(os.environ.get("OPENAI_API_KEY")), "OPENAI_API_KEY configured" if os.environ.get("OPENAI_API_KEY") else "OPENAI_API_KEY missing")

    async def run(self, request: SessionRequest) -> SessionResult:
        if not os.environ.get("OPENAI_API_KEY"):
            return SessionResult(success=False, content="", error="OPENAI_API_KEY missing")
        from openai import AsyncOpenAI

        client = AsyncOpenAI()
        response = await client.responses.create(
            model=request.model or "gpt-5-mini",
            input=request.prompt,
            metadata={key: str(value)[:512] for key, value in request.metadata.items()},
        )
        content = response.output_text
        data = {}
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                data = parsed
        except json.JSONDecodeError:
            pass
        return SessionResult(
            success=True,
            content=content,
            external_session_id=response.id,
            data=data,
            usage=response.usage.model_dump() if response.usage else {},
        )
