from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, Field


class Span(BaseModel):
    span_id: str = Field(default_factory=lambda: uuid4().hex)
    trace_id: str = Field(default_factory=lambda: uuid4().hex)
    consumer_repo: str
    prompt_id: str
    prompt_version: str
    model_alias: str
    model: str
    provider: str
    tokens_input: int | None = None
    tokens_output: int | None = None
    latency_ms: int | None = None
    cost_usd: Decimal | None = None
    retry_count: int = 0
    cache_hit: bool = False
    status: str = "ok"
    call_skipped: bool = False
    retry_unnecessary: bool = False
    error_type: str | None = None
    repaired_attempts: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)

    def as_jsonl(self) -> str:
        return self.model_dump_json()