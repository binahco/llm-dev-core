from __future__ import annotations

from typing import Iterator, Protocol

from pydantic import BaseModel, Field

from .models import TokenUsage


class ProviderRequest(BaseModel):
    model: str
    messages: list[dict] = Field(default_factory=list)
    temperature: float | None = None
    max_tokens: int | None = None


class ProviderResponse(BaseModel):
    text: str
    model: str
    usage: TokenUsage | None = None


class Provider(Protocol):
    name: str

    def complete(self, request: ProviderRequest) -> ProviderResponse: ...

    def stream(self, request: ProviderRequest) -> Iterator[str]: ...