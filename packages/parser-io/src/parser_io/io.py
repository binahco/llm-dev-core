from __future__ import annotations

from pathlib import Path

from .models import ParseError, ParsedDocument
from .readers import parse_by

EXT_FMT = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "markdown",
    ".csv": "csv",
    ".tsv": "csv",
    ".json": "json",
}


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ParseError(f"no se pudo leer: {exc}", source=str(path)) from exc


def parse(source: str | Path, text: str | None = None, fmt: str | None = None) -> ParsedDocument:
    """- `parse(path)` lee y respeta la extensión (fallback al contenido).
    - `parse(source, text)` usa el texto dado (útil para capturas y tests).
    - `fmt` fuerza el formato y evita la detección."""
    path = Path(source)
    if text is None:
        text = _read(path)
    if not path.suffix and fmt is None:
        # Detecta por contenido cuando no hay extensión; el lector acierta o
        # el consumidor fuerza `fmt` explícito.
        doc = parse_by(text, source=str(path), fmt=None)
        return doc
    resolved = fmt or EXT_FMT.get(path.suffix.lower())
    if resolved is None:
        raise ParseError(f"extensión sin lectura asignada: {path.suffix}", source=str(path))
    return parse_by(text, source=str(path), fmt=resolved)


def iter_documents(root: str | Path, extensions: tuple[str, ...] = (".md", ".txt", ".csv", ".json")) -> list[Path]:
    """Archivos de lectura en orden determinista (sorted, recursivo). Poder en
    `content-ray scan --dir`; el consumidor decide el corpus."""
    base = Path(root)
    if base.is_file():
        return [base] if base.suffix.lower() in extensions else []
    return sorted(p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in extensions)