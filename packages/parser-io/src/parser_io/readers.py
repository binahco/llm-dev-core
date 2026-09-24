from __future__ import annotations

import re

from .models import ParseError, ParsedDocument, Section, Table, approx_tokens

SLUG_RE = re.compile(r"[\W_]+", re.UNICODE)
HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)$")
PIPE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")


def _slug(title: str) -> str:
    return SLUG_RE.sub("-", title.lower()).strip("-") or "seccion"


def _scroll_tables(lines: list[str]) -> tuple[list[Table], set[int]]:
    """Celdas de marcas de tabla (líneas de tubería y separadores)."""
    tables: list[Table] = []
    consumed: set[int] = set()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("|") and line.count("|") >= 2:
            candidates = [i]
            j = i + 1
            while j < len(lines) and lines[j].strip():
                if lines[j].lstrip().startswith("|") or PIPE_SEP_RE.match(lines[j]):
                    candidates.append(j)
                else:
                    break
                j += 1
            header_idx = candidates[0]
            sep_idx = None
            for idx in candidates[1:]:
                if PIPE_SEP_RE.match(lines[idx]):
                    sep_idx = idx
                    break
            if sep_idx is not None:
                row_idxs = [idx for idx in candidates if idx > sep_idx]

                def cells(n: int) -> list[str]:
                    return [c.strip() for c in lines[n].strip().strip("|").split("|")]

                headers = cells(header_idx)
                rows = [cells(n) for n in row_idxs]
                for n in candidates:
                    consumed.add(n)
                tables.append(Table(headers=headers, rows=rows, line=header_idx + 1))
                i = j
                continue
        i += 1
    return tables, consumed


def parse_markdown(text: str, *, source: str) -> ParsedDocument:
    lines = text.splitlines()
    if not text.strip():
        raise ParseError("markdown vacío", source=source, line=1)

    title = ""
    for raw in lines:
        m = HEADING_RE.match(raw)
        if m and m.group(1) == "#":
            title = m.group(2).strip()
            break
    if not title:
        title = source.rsplit("/", 1)[-1].split(".", 1)[0]

    tables, _ = _scroll_tables(lines)

    headings = [
        (len(m.group(1)), m.group(2).strip(), idx)  # (nivel, título, línea 1-based)
        for idx, raw in enumerate(lines, start=1)
        if (m := HEADING_RE.match(raw))
    ]
    h1 = [h for h in headings if h[0] == 1]
    if not title and h1:
        title = h1[0][1]
    if not title:
        title = source.rsplit("/", 1)[-1].split(".", 1)[0]

    def section_from_range(level: int, heading_title: str, start: int, end: int) -> Section:
        # Contenido 1-based start+1 .. end (end = siguiente heading del mismo
        # nivel o superior, excluido); líneas de relleno se recortan.
        body_lines = list(lines[start:end])
        trailing = 0
        while body_lines and not body_lines[-1].strip():
            body_lines.pop()
            trailing += 1
        while body_lines and not body_lines[0].strip():
            body_lines.pop(0)
        if not body_lines:
            raise ValueError("sección sin contenido")
        new_end = end - trailing
        text_body = "\n".join(body_lines)
        return Section(
            anchor=_slug(heading_title),
            title=heading_title,
            line_start=start,
            line_end=new_end,
            body=text_body,
            body_tokens=approx_tokens(text_body),
        )

    sections: list[Section] = []
    for i, (level, heading_title, start) in enumerate(headings):
        if level == 1:
            continue  # el título del documento no es una sección
        end = len(lines)
        for j in range(i + 1, len(headings)):
            if headings[j][0] <= level:
                end = headings[j][2] - 1
                break
        if end <= start:
            continue
        try:
            sections.append(section_from_range(level, heading_title, start, end))
        except ValueError:
            continue

    if not sections:
        # Documento sin headings: una sección implícita con todo el contenido.
        parts = [ln for ln in lines if ln.strip()]
        if not parts:
            raise ParseError("markdown vacío", source=source, line=1)
        sections.append(
            Section(
                anchor=_slug(title),
                title=title,
                line_start=1,
                line_end=len(lines),
                body="\n".join(parts),
                body_tokens=approx_tokens("\n".join(parts)),
            )
        )

    return ParsedDocument(
        source=source,
        format="markdown",
        title=title,
        sections=sections,
        tables=tables,
        lines=len(lines),
        approx_tokens=approx_tokens(text),
        meta={},
    )


def parse_csv(text: str, *, source: str) -> ParsedDocument:
    import csv
    import io

    if not text.strip():
        raise ParseError("csv vacío", source=source, line=1)
    rows: list[list[str]] = []
    try:
        for index, line in enumerate(csv.reader(io.StringIO(text)), start=1):
            rows.append(line)
    except csv.Error as exc:
        raise ParseError(f"csv inválido: {exc}", source=source, line=index) from exc
    if not rows or all(not r or all(not c for c in r) for r in rows):
        raise ParseError("csv sin filas con contenido", source=source, line=1)
    headers = [c.strip() for c in rows[0]]
    data_rows = [[c for c in r] for r in rows[1:]]
    return ParsedDocument(
        source=source,
        format="csv",
        title=source.rsplit("/", 1)[-1].split(".", 1)[0],
        sections=[],
        tables=[Table(headers=headers, rows=data_rows, line=1)],
        lines=len(rows),
        approx_tokens=approx_tokens(text),
        meta={"header_row": True},
    )


def parse_json(text: str, *, source: str) -> ParsedDocument:
    import json

    if not text.strip():
        raise ParseError("json vacío", source=source, line=1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ParseError(f"json inválido: {exc.msg}", source=source, line=exc.lineno) from exc

    sections: list[Section] = []
    items = data.values() if isinstance(data, dict) else [data]
    if isinstance(data, dict):
        for key in data:
            encoded = json.dumps(data[key], ensure_ascii=False, default=str)
            sections.append(
                Section(
                    anchor=_slug(str(key)),
                    title=str(key),
                    line_start=1,
                    line_end=len(text.splitlines()),
                    body=encoded,
                    body_tokens=approx_tokens(encoded),
                )
            )
    else:
        encoded = json.dumps(data, ensure_ascii=False, default=str)
        sections.append(
            Section(
                anchor="items",
                title="items",
                line_start=1,
                line_end=len(text.splitlines()),
                body=encoded,
                body_tokens=approx_tokens(encoded),
            )
        )
    return ParsedDocument(
        source=source,
        format="json",
        title=source.rsplit("/", 1)[-1].split(".", 1)[0],
        sections=sections,
        tables=[],
        lines=len(text.splitlines()),
        approx_tokens=approx_tokens(text),
        meta={"top_level_keys": list(data) if isinstance(data, dict) else []},
    )


def parse_by(text: str, *, source: str, fmt: str | None = None) -> ParsedDocument:
    fmt = fmt or _sniff(text)
    if fmt == "markdown":
        return parse_markdown(text, source=source)
    if fmt == "csv":
        return parse_csv(text, source=source)
    if fmt == "json":
        return parse_json(text, source=source)
    raise ParseError(f"formato no soportado: {fmt!r}", source=source, line=1)


def _sniff(text: str) -> str:
    stripped = text.lstrip()
    if not stripped or text.isspace():
        return "markdown"
    if stripped.startswith("{") or stripped.startswith("["):
        return "json"
    lines = stripped.splitlines()
    for delim in (",", "\t"):
        if lines and lines[0].count(delim) >= 1:
            counts = {ln.count(delim) for ln in lines[:5]}
            if len(counts) == 1:
                return "csv"
    return "markdown"