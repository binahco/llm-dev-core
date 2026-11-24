"""El puente hacia `web-api-base` (ADR-13): la base no cambia, auth-base se enchufa."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from web_api_base import ErrorBody

from .errors import AuthError
from .models import Principal
from .store import KeyStore


def register_auth(app: FastAPI) -> None:
    """`AuthError` sale con el cuerpo de error uniforme de la base. Un 401 siempre pide `Bearer`."""

    @app.exception_handler(AuthError)
    async def _auth_error(request: Request, exc: AuthError):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        body = ErrorBody(error=exc.error, detail=exc.detail, code=exc.status_code)
        return JSONResponse(body.model_dump(), status_code=exc.status_code, headers=headers)


def require(store: KeyStore, scope: str) -> Callable[..., Principal]:
    """Dependencia de FastAPI: la ruta solo corre si la clave autentica y tiene `scope`."""

    def _acceso(request: Request) -> Principal:
        return store.check(_credencial(request), scope)

    return _acceso


def _credencial(request: Request) -> str | None:
    """La clave del header `Authorization: Bearer <clave>`.

    None si no hay header. Si lo hay pero no es Bearer (o viene vacío), se entrega como
    mal formado: auth-base solo habla de claves, no de otros esquemas.
    """
    header = request.headers.get("authorization", "").strip()
    if not header:
        return None
    esquema, _, parametro = header.partition(" ")
    return parametro.strip() if esquema.lower() == "bearer" else ""
