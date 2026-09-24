# Contrato mínimo — `parser-io`

- **Fecha:** 2026-10-01
- **Estado:** aceptada
- **Origen:** el calendario C1–C18 (§5): `parser-io` (C9) es la **capa de lectura**
  de archivos que necesitarán `docs-gen` (sem. 12), `vector-core` (sem. 16),
  `diff-engine` (sem. 19) y `scraper` (sem. 28) del lado de la entrada.
  `schema-validate` cubre la **salida** JSON del LLM; nadie cubre la **entrada**
  de archivos reales — ese es el hueco.
- **Implementada en:** semana 10 (`packages/parser-io` v0.1.0, nacida dentro de
  `content-ray`)

Los consumidores hoy reciben texto ya listo (git diffs, logs, cassettes). Cuando
el proyecto meta archivos de verdad (repos, tablas, dumps, docs de clientes), cada
consumidor tendría que re-implementar "leer el archivo": detectar formato, separar
secciones, ubicar filas, medir cuánto cabe en un prompt. `parser-io` lo hace una
vez, determinista y con mapeo a línea — la base sobre la que `docs-gen` y
`vector-core` construirán sin reinventarlo.

## 1. API conceptual

```python
from parser_io import ParseError, ParsedDocument, iter_documents, parse

doc = parse("docs/ARCHITECTURE.md")                # lee y detecta por extensión
doc2 = parse("data/equipos.csv", text=csv_text)    # o con el texto ya en mano
for section in doc.sections:
    print(section.anchor, section.line_start, section.line_end, section.body_tokens)
table = doc.tables[0]                              # headers / rows / line

source = iter_documents("corpus/")                 # list[Path] determinista
```

- `ParsedDocument`: `source`, `format` (`markdown`/`csv`/`json`), `title`,
  `sections[]` (anchor, título, `line_start`/`line_end`, cuerpo, `body_tokens`),
  `tables[]` (headers, filas, línea), `lines`, `approx_tokens`, `meta`.
- `parse(source[, text, fmt])`: respeta la extensión; sin extensión sniffa por
  contenido; `fmt` fuerza. Errores → `ParseError` con `source` y `line`.
- `ParseError` tipa lo que el consumidor debe triagear (archivo ajeno, encoding
  inválido, JSON roto con línea): nunca un `Exception` genérico.
- `approx_tokens`: heurística ~1 token / 4 chars (colapso de espacios), para que
  el consumidor decida ventanas antes de llamar al LLM (`vector-core` lo
  transcoderá con `tokenizers`).

## 2. Reglas

- **La hoja no cambia y el formato no opina:** `parser-io` no depende de ningún
  módulo del core (solo `pydantic` + stdlib) y **no** importa `llm-client`.
  El sanitizado (`secure-base`) y el LLM se componen en el consumidor.
- **Determinismo (D4):** el mismo `source` + contenido produce siempre el mismo
  `ParsedDocument` (orden de secciones, anclas, tablas y líneas estables). Los
  tests no tocan disco salvo `iter_documents`, que es sorted.
- **Formato mínimo honesto:** tres lectores reales (`markdown`, `csv`, `json`)
  con pruebas de exactitud; HTML/PDF no se prometen hasta que un consumidor los
  necesite de verdad (D9, `scraper`).
- **El lector captura, no opina:** tablas como `Table` y también dentro del
  `body` de su sección; el consumidor elige qué pasar al prompt.

## 3. Qué NO contrata este documento

- **Transcodificación de tokens real** (`tokenizers`/BPE): solo la heurística
  `approx_tokens`; el conteo exacto llega con `vector-core`.
- **Chunking/RAG** segmentado para embeddings: `vector-core` (sem. 16) define
  ventanas sobre `ParsedDocument`, no al revés.
- **PDF/HTML/DOCX**: lectores futuros, solo si un consumidor lo exige
  (`scraper` sem. 28 es candidato seguro para HTML).
- **La parte de red y un "pipeline de ingesta"** con validación, persistencia y
  monitoreo: `scraper` + `bot-base` lo componen.

## 4. Criterio de aceptación del contrato (semana 10)

- [x] `parse` por extensión y por contenido (sin extensión); `fmt` explícito.
- [x] Lectores `markdown` (secciones/tablas con `line_start`/`line_end`),
      `csv` (cabeceras + filas) y `json` (secciones por clave top-level).
- [x] `ParseError` con `source` + `line` para JSON inválido y extensiones sin lectura.
- [x] `approx_tokens` determinista; `iter_documents` determinista y recursivo.
- [x] Primer consumidor real: `content-ray` (sem. 10) — escanea los `.md` de
      `llm-dev-core`, ventanas por sección y digest LLM validado.