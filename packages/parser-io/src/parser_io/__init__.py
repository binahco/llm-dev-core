"""parser-io: capa de lectura de archivos (ADR-9).

Normaliza markdown/csv/json a un `ParsedDocument` determinista (secciones,
tablas, mapeo a línea, presupuesto de tokens). Hoja del core: pydantic +
stdlib, **no** importa `llm-client` — el sanitizado (`secure-base`) y el LLM
se componen en el consumidor.

    from parser_io import ParseError, ParsedDocument, iter_documents, parse

    doc = parse("docs/ARCHITECTURE.md")
    for section in doc.sections:
        print(section.title, section.line_start, section.body_tokens)
"""

from .io import iter_documents, parse
from .models import ParseError, ParsedDocument, Section, Table, approx_tokens
from .readers import parse_csv, parse_json, parse_markdown

__all__ = [
    "ParseError",
    "ParsedDocument",
    "Section",
    "Table",
    "approx_tokens",
    "iter_documents",
    "parse",
    "parse_csv",
    "parse_json",
    "parse_markdown",
]