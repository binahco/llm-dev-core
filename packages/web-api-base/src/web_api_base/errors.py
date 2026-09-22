from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from llm_client import CompletionResult, CostCapExceeded, ValidationResult

from .response import _ErrorResponse

LLMProviderError = ConnectionError  # alias: fallos de red/proveedor → 502


class LLMHTTPError(Exception):
    """Traduce un fallo del pipeline LLM a un status HTTP uniforme."""

    def __init__(self, status_code: int, error: str, detail: Any = None) -> None:
        super().__init__(error)
        self.status_code = status_code
        self.error = error
        self.detail = detail


def validate_response(result: CompletionResult) -> CompletionResult:
    """Regla 3 (§3): la salida del LLM es input no confiable — solo pasa la validada."""
    if not result.validation.ok:
        raise LLMHTTPError(
            422,
            "salida_no_validada",
            detail=result.validation.errors,
        )
    return result


def result_body(result: CompletionResult) -> dict[str, Any]:
    return {
        "span_id": result.span_id,
        "prompt_id": result.prompt_id,
        "prompt_version": result.prompt_version,
        "model": result.model,
        "provider": result.provider,
        "content": result.raw_text,
        "parsed": result.parsed.model_dump() if result.parsed is not None else None,
        "validation_ok": result.validation.ok,
        "validation_errors": result.validation.errors,
        "cost_usd": str(result.cost_usd),
        "latency_ms": result.latency_ms,
    }


def error_status(exc: Exception) -> tuple[int, str, Any]:
    """Normaliza excepciones del pipeline LLM a (status, mensaje corto, detalle)."""
    if isinstance(exc, LLMHTTPError):
        return exc.status_code, exc.error, exc.detail
    if isinstance(exc, CostCapExceeded):
        return 429, "presupuesto_excedido", f"costo {exc.cost} > cap {exc.cap}"
    if isinstance(exc, ValidationError):
        return 422, "peticion_invalida", exc.errors()
    if isinstance(exc, LLMProviderError):
        return 502, "proveedor_indisponible", str(exc)
    return 500, "error_interno", str(exc)


def register_error_handlers(app) -> None:
    @app.exception_handler(LLMHTTPError)
    async def _llm_http(request: Request, exc: LLMHTTPError):
        return _ErrorResponse(error=exc.error, detail=exc.detail, status_code=exc.status_code)

    @app.exception_handler(CostCapExceeded)
    async def _cost_cap(request: Request, exc: CostCapExceeded):
        return _ErrorResponse(error="presupuesto_excedido", detail=f"costo {exc.cost} > cap {exc.cap}", status_code=429)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        return _ErrorResponse(error="error_interno", detail=str(exc), status_code=500)

    # los JSONResponse devueltos por handlers no deben ir envueltos por el cliente de errores de FastAPI
    app.add_exception_handler(LLMProviderError, lambda req, exc: JSONResponse(
        {"error": "proveedor_indisponible", "detail": str(exc), "code": 502}, status_code=502,
    ))