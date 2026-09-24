from __future__ import annotations

import json
from pathlib import Path

import pytest
from parser_io import (
    ParseError,
    ParsedDocument,
    approx_tokens,
    iter_documents,
    parse,
    parse_csv,
    parse_json,
    parse_markdown,
)

MD = """\
# Proyecto de ejemplo

## Instalación

Ejecute `make validate`.

## Uso

| comando | efecto      |
| ------- | ----------- |
| scan    | lee archivos |
| sample  | ventana      |

### Métricas

- costo
- latencia
"""


def test_markdown_secciones_con_mapeo_a_linea() -> None:
    doc = parse_markdown(MD, source="docs/ejemplo.md")
    assert doc.format == "markdown"
    assert doc.title == "Proyecto de ejemplo"
    titles = [(s.title, s.line_start, s.line_end) for s in doc.sections]
    assert titles[0] == ("Instalación", 3, 5)
    assert titles[1] == ("Uso", 7, 17)
    assert titles[-1][0] == "Métricas"
    assert doc.lines == len(MD.splitlines())


def test_markdown_tabla_extraida_con_linea() -> None:
    doc = parse_markdown(MD, source="docs/ejemplo.md")
    assert len(doc.tables) == 1
    table = doc.tables[0]
    assert table.headers == ["comando", "efecto"]
    assert table.rows == [["scan", "lee archivos"], ["sample", "ventana"]]
    assert table.line == 9


def test_markdown_ancla_esluginizada() -> None:
    doc = parse_markdown("# Título\n\n## Métricas clave\n\ncosto: alto\n", source="a.md")
    assert [s.anchor for s in doc.sections] == ["métricas-clave"]


def test_csv_cabeceras_y_filas() -> None:
    csv_text = "nombre,equipo\nana,core\nbea,flota\n"
    doc = parse_csv(csv_text, source="data/equipos.csv")
    assert doc.format == "csv"
    assert doc.tables[0].headers == ["nombre", "equipo"]
    assert doc.tables[0].rows == [["ana", "core"], ["bea", "flota"]]
    assert doc.meta == {"header_row": True}


def test_csv_datillas_con_comas_entre_comillas() -> None:
    csv_text = 'a,b\n"x,1",y\n'
    doc = parse_csv(csv_text, source="data/raro.csv")
    assert doc.tables[0].rows == [["x,1", "y"]]


def test_json_secciones_por_clave_top_level() -> None:
    text = json.dumps({"una": [1, 2], "dos": {"b": 3}})
    doc = parse_json(text, source="data/datos.json")
    assert doc.format == "json"
    assert [s.title for s in doc.sections] == ["una", "dos"]
    assert doc.meta["top_level_keys"] == ["una", "dos"]


def test_parse_respeta_extension() -> None:
    assert parse("data/a.md", text="# Hola\n").format == "markdown"
    assert parse("data/b.csv", text="x,y\n1,2\n").format == "csv"
    assert parse("data/c.json", text='{"k": 1}').format == "json"


def test_parse_detecta_por_contenido_sin_extension() -> None:
    doc = parse("data/sin-ext", text='{"clave": true}')
    assert doc.format == "json"


def test_extension_desconocida_lanza_con_source() -> None:
    with pytest.raises(ParseError) as exc:
        parse("data/foto.png", text="zzz")
    assert "foto.png" in str(exc.value)


def test_jsoninvalido_lleva_linea() -> None:
    with pytest.raises(ParseError) as exc:
        parse_json("{broken", source="d.json")
    assert exc.value.line is not None


def test_aprox_tokens_determinista() -> None:
    assert approx_tokens("hola mundo") == approx_tokens("hola mundo")
    assert approx_tokens("") == 1
    assert approx_tokens("a" * 40) == 10


def test_iter_documents_ordenado_y_recursivo(tmp_path: Path) -> None:
    (tmp_path / "b").mkdir()
    (tmp_path / "a.md").write_text("# a")
    (tmp_path / "b" / "c.csv").write_text("x\n1\n")
    (tmp_path / "skip.json").write_text("{}")
    (tmp_path / "otro.log").write_text("zzz")
    assert iter_documents(tmp_path) == [tmp_path / "a.md", tmp_path / "b" / "c.csv", tmp_path / "skip.json"]


def test_documento_consistente_y_con_token_budget(tmp_path: Path) -> None:
    path = tmp_path / "m.md"
    path.write_text(MD)
    doc = parse(path)
    assert isinstance(doc, ParsedDocument)
    assert doc.approx_tokens > 0
    assert all(s.body_tokens > 0 for s in doc.sections)