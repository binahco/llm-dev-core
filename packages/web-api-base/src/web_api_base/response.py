from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorBody(BaseModel):
    error: str
    detail: Any | None = None
    code: int


class HealthBody(BaseModel):
    status: str
    service: str
    core_version: str
    provider: str
    model_alias: str


class LLMResultBody(BaseModel):
    span_id: str
    prompt_id: str
    prompt_version: str
    model: str
    provider: str
    content: str
    parsed: Any | None = None
    validation_ok: bool
    validation_errors: list[str]
    cost_usd: str
    latency_ms: int


class _ErrorResponse(JSONResponse):
    def __init__(self, *, error: str, detail: Any = None, status_code: int) -> None:
        body = ErrorBody(error=error, detail=detail, code=status_code)
        super().__init__(body.model_dump(), status_code=status_code)