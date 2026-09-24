from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field


def approx_tokens(text: str) -> int:
    """Heurística de presupuesto de tokens (§10, parser-io): ~1 token por 4 chars
    del texto colapsado, mínimo 1. Determinista; un transcoder real es de `tokenizers`
    (fuera del core hasta `vector-core`)."""
    collapsed = re.sub(r"\s+", " ", text).strip()
    return max(1, round(len(collapsed) / 4))


class Section(BaseModel):
    anchor: str
    title: str
    line_start: int
    line_end: int
    body: str
    body_tokens: int = Field(default=0)


class Table(BaseModel):
    headers: list[str]
    rows: list[list[str]]
    line: int


class ParsedDocument(BaseModel):
    """Documento normalizado por la capa de lectura (ADR-9). Determinista:
    el mismo `source` + contenido produce siempre el mismo `ParsedDocument`."""

    source: str
    format: Literal["markdown", "csv", "json"]
    title: str
    sections: list[Section]
    tables: list[Table]
    lines: int
    approx_tokens: int
    meta: dict[str, Any] = Field(default_factory=dict)


class ParseError(ValueError):
    """Error tipado con `source` y `line` para que el consumidor haga triaje."""

    def __init__(self, message: str, *, source: str | None = None, line: int | None = None) -> None:
        self.source = source
        self.line = line
        where = ""
        if source is not None:
            where = f" en {source}"
        if line is not None:
            where += f":{line}"
        super().__init__(f"{message}{where}")