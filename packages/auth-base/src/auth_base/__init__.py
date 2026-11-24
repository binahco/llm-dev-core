"""auth-base: acceso por clave de API con permisos exactos (ADR-13).

    from fastapi import Depends
    from auth_base import KeyStore, register_auth, require

    store = KeyStore()
    issued = store.issue("fleet-bot", scopes=["llm:complete"])   # el secreto, una sola vez
    register_auth(app)                                            # 401/403 con el error uniforme

    @app.post("/llm", dependencies=[Depends(require(store, "llm:complete"))])
    def llm(req): ...

El núcleo (`KeyStore`) es una hoja — stdlib + pydantic, reloj inyectable — y no conoce
HTTP. `register_auth`/`require` son el puente hacia una app de `web-api-base`, que no
cambia. La llave la trae el cliente en `Authorization: Bearer <key_id>.<secreto>`.
"""

from .clock import AuthClock, RealClock
from .errors import NO_AUTENTICADO, SIN_PERMISO, AuthError
from .http import register_auth, require
from .models import AuthEvent, IssuedKey, KeyRecord, Principal
from .store import KeyStore, verifier_of

__all__ = [
    "NO_AUTENTICADO",
    "SIN_PERMISO",
    "AuthClock",
    "AuthError",
    "AuthEvent",
    "IssuedKey",
    "KeyRecord",
    "KeyStore",
    "Principal",
    "RealClock",
    "register_auth",
    "require",
    "verifier_of",
]
