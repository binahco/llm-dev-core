from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from llm_client import CompletionRequest, LlmClient

from .errors import result_body, validate_response
from .response import _ErrorResponse


class CompleteRequest(BaseModel):
    """Contrato de entrada para el endpoint LLM genérico de web-api-base.

    `variables` se renderiza con el `renderer` del consumidor (cableado dentro de
    `LlmClient`); `response_schema=None` desactiva la validación (§3 opt-out explícito).
    """

    prompt_id: str
    prompt_version: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    model_alias: str = "fast"
    response_schema: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    tags: list[str] = Field(default_factory=list)


def llm_complete(client: LlmClient, req: CompleteRequest, *, require_valid: bool = True):
    """Ejecuta el pipeline LLM completo y valida la salida antes de responder."""
    result = client.complete(
        CompletionRequest(
            prompt_id=req.prompt_id,
            prompt_version=req.prompt_version,
            variables=req.variables,
            model_alias=req.model_alias,
            response_schema=req.response_schema,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            tags=req.tags,
        )
    )
    if require_valid:
        validate_response(result)
    return result_body(result)


def add_llm_endpoint(app: FastAPI, client: LlmClient, *, path: str = "/llm") -> None:
    """Registra el endpoint LLM genérico de la base (POST {path})."""

    @app.post(path)
    async def _llm(req: CompleteRequest):
        return llm_complete(client, req)


def sse_response(client: LlmClient, req: CompleteRequest, *, require_valid: bool = True) -> StreamingResponse:
    """Respuesta en Server-Sent Events: múltiples eventos `data:` y un evento `done`.

    `llm-client` entrega resultados completos (con retries/reparación internos), así que
    el streaming aquí es por-evento, no por-token: cada `data:` transporta un JSON
    autocontenido. La fragmentación por token llegará cuando un proveedor lo exponga.
    """
    chunk = llm_complete(client, req, require_valid=require_valid)

    def _gen():
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")