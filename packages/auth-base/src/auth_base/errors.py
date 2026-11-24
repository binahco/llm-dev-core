from __future__ import annotations

from typing import Any

NO_AUTENTICADO = "no_autenticado"
SIN_PERMISO = "sin_permiso"


class AuthError(Exception):
    """El acceso se negó.

    Al que llama solo le llegan `status_code`, `error` y `detail`. La razón fina
    (revocada, vencida, secreto incorrecto) va a la auditoría, no a la respuesta.
    """

    def __init__(self, status_code: int, error: str, *, detail: Any = None) -> None:
        super().__init__(error)
        self.status_code = status_code
        self.error = error
        self.detail = detail
