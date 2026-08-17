from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SessionRequest(BaseModel):
    prompt: str
    working_directory: Path
    title: str
    model: str | None = None
    external_session_id: str | None = None
    timeout_seconds: int = 1800
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionResult(BaseModel):
    success: bool
    content: str
    external_session_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class Provider(ABC):
    name: str

    @abstractmethod
    async def healthcheck(self) -> tuple[bool, str]:
        raise NotImplementedError

    @abstractmethod
    async def run(self, request: SessionRequest) -> SessionResult:
        raise NotImplementedError
