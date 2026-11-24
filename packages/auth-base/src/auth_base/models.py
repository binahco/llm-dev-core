from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Outcome = Literal["ok", "no_autenticado", "sin_permiso"]

# Por qué falló un acceso. Es información del operador: nunca viaja al que llama.
AUSENTE = "ausente"
MALFORMADA = "malformada"
DESCONOCIDA = "desconocida"
SECRETO_INCORRECTO = "secreto_incorrecto"
REVOCADA = "revocada"
VENCIDA = "vencida"


class Principal(BaseModel):
    """Quién llama, una vez autenticado: el cliente, la clave concreta y lo que esa clave permite."""

    client: str
    key_id: str
    scopes: frozenset[str]


class KeyRecord(BaseModel):
    """Lo que se guarda de una clave. El secreto no: solo su huella."""

    key_id: str
    client: str
    scopes: list[str]
    verifier: str = Field(repr=False)
    created_at: float
    expires_at: float | None = None
    revoked: bool = False

    @field_validator("scopes")
    @classmethod
    def _ordenados_y_sin_repetir(cls, scopes: list[str]) -> list[str]:
        return sorted(set(scopes))

    def public(self) -> dict:
        """La vista que se puede listar o responder por HTTP: sin la huella."""
        return self.model_dump(exclude={"verifier"}, mode="json")


class IssuedKey(BaseModel):
    """Lo que devuelve `issue`. El secreto aparece aquí una sola vez; después nadie lo tiene."""

    key: str
    key_id: str
    client: str
    scopes: list[str]
    expires_at: float | None = None


class AuthEvent(BaseModel):
    """La evidencia de un intento de acceso: quién, para qué y cómo salió. Nunca el secreto."""

    at: float
    outcome: Outcome
    client: str | None = None
    key_id: str | None = None
    scope: str | None = None
    reason: str = ""
