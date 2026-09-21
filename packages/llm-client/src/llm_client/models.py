from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int


class ValidationResult(BaseModel):
    ok: bool
    errors: list[str] = Field(default_factory=list)
    parsed: Any = None


class CompletionRequest(BaseModel):
    prompt_id: str
    variables: dict[str, Any] = Field(default_factory=dict)
    model_alias: str
    prompt_version: str | None = None
    response_schema: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    tags: list[str] = Field(default_factory=list)


class CompletionResult(BaseModel):
    raw_text: str
    parsed: Any = None
    validation: ValidationResult
    usage: TokenUsage | None = None
    cost_usd: Decimal
    latency_ms: int
    prompt_id: str
    prompt_version: str
    model_alias: str
    model: str
    provider: str
    span_id: str