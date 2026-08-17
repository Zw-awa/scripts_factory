from __future__ import annotations

from .base import Provider
from .fake import FakeProvider
from .opencode import OpenCodeProvider
from .openai_responses import OpenAIResponsesProvider


def build_provider(name: str) -> Provider:
    providers: dict[str, type[Provider]] = {
        "fake": FakeProvider,
        "opencode": OpenCodeProvider,
        "openai": OpenAIResponsesProvider,
    }
    try:
        return providers[name]()
    except KeyError as exc:
        raise ValueError(f"Unknown provider: {name}. Expected one of: {', '.join(sorted(providers))}") from exc
