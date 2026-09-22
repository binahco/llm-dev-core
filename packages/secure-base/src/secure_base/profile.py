from __future__ import annotations

from pydantic import BaseModel

from .detectors import scan
from .findings import Finding

DATA_TYPE_NAMES = ("email", "phone", "ipv4", "credit_card", "aws_access_key", "github_token", "private_key", "bearer", "url_userinfo")


class SecurityProfile(BaseModel):
    """Qué tipos de datos declara manejar el consumidor (§3.1 y futuro lint de ci-pack)."""

    data_types: list[str]


def assert_redacted(text: str, profile: SecurityProfile | None = None) -> list[Finding]:
    """Devuelve hallazgos que siguen en claro en `text`.

    Si el texto se va a enviar a un proveedor externo, un resultado no vacío es una violación.
    Con `profile`, filtra a los tipos declarados por el consumidor.
    """
    findings = scan(text)
    if profile is None:
        return findings
    declared = set(profile.data_types)
    return [f for f in findings if f.type in declared]