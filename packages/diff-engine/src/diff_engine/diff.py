"""diff-engine — comparación estructural determinista (ADR-10).

La hoja no cambia: stdlib + pydantic, nada de `llm-client`. Difflib es determinista
(D4): mismas entradas, mismo diff, sin relojes ni aleatoriedad. Los campos volátiles
(timestamps, ids, latencias) se declaran y se ignoran: compararlos mediría el ruido
de la corrida, no el cambio.
"""

from __future__ import annotations

import difflib
from typing import Literal

from pydantic import BaseModel, Field

# Campos que cambian en cada corrida aunque la respuesta no cambie (ADR-10 §2).
VOLATILE_FIELDS: tuple[str, ...] = (
    "timestamp",
    "generated_el",
    "generado_el",
    "span_id",
    "trace_id",
    "latency_ms",
    "request_id",
)


class Hunk(BaseModel):
    """Un bloque de cambio entre dos textos, en líneas."""

    op: Literal["igual", "cambiada", "agregada", "eliminada"]
    a_start: int
    b_start: int
    lineas_a: list[str] = []
    lineas_b: list[str] = []

    @property
    def corto(self) -> str:
        return f"{self.op}@a{self.a_start}/b{self.b_start} -{len(self.lineas_a)} +{len(self.lineas_b)}"


class FieldDiff(BaseModel):
    campo: str
    igual: bool
    similitud: float = Field(ge=0.0, le=1.0)


class DiffReport(BaseModel):
    """Veredicto de comparar dos registros (p. ej. dos llamadas grabadas)."""

    igual: bool
    similitud_texto: float = Field(ge=0.0, le=1.0)
    campos: list[FieldDiff] = []
    hunks: list[Hunk] = []
    volatiles_ignorados: list[str] = []


def text_similarity(a: str, b: str) -> float:
    """Similitud de textos en [0, 1]; determinista."""
    if a == b:
        return 1.0
    return difflib.SequenceMatcher(a=a, b=b).ratio()


def diff_text(a: str, b: str) -> list[Hunk]:
    """Hunks línea a línea entre dos textos. Las líneas contextuales no se devuelven."""
    al, bl = a.splitlines(), b.splitlines()
    matcher = difflib.SequenceMatcher(a=al, b=bl)
    hunks: list[Hunk] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        op: Literal["cambiada", "agregada", "eliminada"] = (
            "cambiada" if tag == "replace" else "agregada" if tag == "insert" else "eliminada"
        )
        hunks.append(
            Hunk(op=op, a_start=i1 + 1, b_start=j1 + 1, lineas_a=al[i1:i2], lineas_b=bl[j1:j2])
        )
    return hunks


def diff_records(
    a: dict,
    b: dict,
    *,
    volatiles: tuple[str, ...] = VOLATILE_FIELDS,
) -> DiffReport:
    """Compara dos registros campo a campo. Los volátiles declarados se ignoran y se
    listan; los campos de texto se comparan con similitud, el resto con igualdad."""
    campos: list[FieldDiff] = []
    volatiles_vistos: list[str] = []
    for key in sorted(set(a) | set(b)):
        if key in volatiles:
            volatiles_vistos.append(key)
            continue
        va, vb = a.get(key), b.get(key)
        if isinstance(va, str) and isinstance(vb, str):
            campos.append(FieldDiff(campo=key, igual=va == vb, similitud=text_similarity(va, vb)))
        else:
            campos.append(FieldDiff(campo=key, igual=va == vb, similitud=1.0 if va == vb else 0.0))

    texto_a = next((c for c in campos if c.campo in ("text", "texto", "response", "respuesta")), None)
    similitud = texto_a.similitud if texto_a else (1.0 if all(c.igual for c in campos) else 0.0)
    cuerpo_a = str(a.get("text", a.get("texto", "")))
    cuerpo_b = str(b.get("text", b.get("texto", "")))
    return DiffReport(
        igual=all(c.igual for c in campos),
        similitud_texto=round(similitud, 4),
        campos=campos,
        hunks=diff_text(cuerpo_a, cuerpo_b),
        volatiles_ignorados=volatiles_vistos,
    )
