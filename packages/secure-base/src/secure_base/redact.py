from __future__ import annotations

from pydantic import BaseModel

from .detectors import scan
from .findings import Finding


class RedactResult(BaseModel):
    text: str
    findings: list[Finding]


def detect(text: str) -> list[Finding]:
    """Detecta secretos/PII sin redactar. Alimenta reportes y lints."""
    return scan(text)


def redact(text: str) -> RedactResult:
    """Enmascara de forma unidireccional y determinista: el secreto crudo no queda en el texto."""
    findings = scan(text)
    counters: dict[str, int] = {}
    pieces: list[str] = []
    cursor = 0
    for f in findings:
        pieces.append(text[cursor : f.offset])
        counters[f.type] = counters.get(f.type, 0) + 1
        pieces.append(f"[REDACTED:{f.type}:{counters[f.type]}]")
        cursor = f.offset + f.length
    pieces.append(text[cursor:])
    return RedactResult(text="".join(pieces), findings=findings)


def sanitize_for_prompt(text: str) -> RedactResult:
    """Alias semántico para el renderer: nada sensible entra al prompt."""
    return redact(text)