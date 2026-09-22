from __future__ import annotations

from fastapi import FastAPI

from llm_client import LlmClient

from .errors import register_error_handlers
from .llm_route import CompleteRequest, add_llm_endpoint, llm_complete, sse_response
from .response import _ErrorResponse


def create_app(
    title: str,
    version: str,
    *,
    client: LlmClient,
    health_extra: dict | None = None,
    llm_path: str = "/llm",
    enable_llm_endpoint: bool = True,
) -> FastAPI:
    """App FastAPI LLM-ready de `web-api-base`.

    Base mínima reutilizable para servir capacidades LLM por HTTP:
      - `/health` (liveness) con versión y estado del proveedor,
      - errores uniformes (ADRD-5): presupuesto→429, validación→422, proveedor→502, 500 resto,
      - endpoint LLM genérico `POST {llm_path}` (llm-client + validez como gate),
      - SSE opcional vía `sse_response`.

    Auth, rate-limit y observabilidad no son de esta semana (suceden en `auth-base`
    sem 25, `cache-ratelimit` sem 8 y `cost-obs` sem 39).
    """
    app = FastAPI(title=title, version=version)

    @app.get("/health", tags=["core"])
    async def health():
        body = {
            "status": "ok",
            "service": title,
            "core_version": version,
            "provider": client.provider.name,
            "model_alias": list((client.model_aliases or {}).keys()),
        }
        if health_extra:
            body.update(health_extra)
        return body

    if enable_llm_endpoint:
        add_llm_endpoint(app, client, path=llm_path)

    register_error_handlers(app)
    return app