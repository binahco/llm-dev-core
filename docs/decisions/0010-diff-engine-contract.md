# Contrato mínimo — `diff-engine`

- **Fecha:** 2026-11-20
- **Estado:** aceptada
- **Origen:** el calendario C1–C18 (§5): `diff-engine` (C12) es la base para comparar
  artefactos de la flota — cassettes de una misma sesión de eval, salidas de prompts
  entre versiones, documentos entre tags. Nació vencida esa deuda: su seed iba en la
  sem. 19 y esa semana pagó la verificación (F0–F4).
- **Implementada en:** semana 19 (`packages/diff-engine` v0.1.0, dentro de `llm-dev-core`
  v1.2.0; primer consumidor: `cassette-diff`)

Comparar dos textos con los ojos encuentra lo que uno espera encontrar. La flota necesita
comparar artefactos que nadie mira línea a línea: dos grabaciones del mismo prompt, la
salida de un prompt antes y después de editarlo. Esa comparación tiene que ser
**determinista** y tiene que saber **qué no comparar**: un `timestamp` distinto no es deriva.

## 1. API conceptual

```python
from diff_engine import diff_records, diff_text, text_similarity, VOLATILE_FIELDS

report = diff_records(llamada_a, llamada_b)     # campos, hunks, veredicto
report.igual                # False si algún campo no volátil cambió
report.similitud_texto      # [0, 1] sobre el campo de respuesta
report.hunks                # bloques cambiada/agregada/eliminada con líneas
report.volatiles_ignorados  # lo que NO se comparó, a la vista

hunks = diff_text("antes…", "después…")          # hunks línea a línea
ratio = text_similarity("a", "b")                # [0, 1], determinista
```

## 2. Reglas

- **La hoja no cambia:** `diff-engine` no depende de ningún módulo del core (stdlib +
  `pydantic`), como `bot-base`. El que compara no llama modelos; el consumidor compone.
- **Determinismo (D4):** `difflib` puro, sin relojes, sin aleatoriedad, sin red: mismas
  entradas, mismo diff. Dos corridas devuelven el mismo reporte byte a byte.
- **Volátiles declarados, no adivinados:** `VOLATILE_FIELDS` (timestamps, ids, latencias)
  se ignoran por defecto y **se listan en el reporte**: ignorar en silencio es mentir con
  estadística. Quien compare otra cosa, pasa los suyos (`volatiles=`).
- **Campos de texto por similitud, el resto por igualdad:** un texto que cambió de
  palabra no es un booleano; un `usage` que cambió de número, sí.
- **Hunks con líneas, no parches:** el consumidor muestra lo que cambió; aplicar el
  cambio es trabajo de un `patcher` que nadie ha pedido.

## 3. Qué NO contrata este documento

- **Similitud semántica** (embeddings, significado): eso es `vector-core` (C11), con su
  propio ADR cuando se siembre. Aquí "parecido" es textual, medible y reproducible.
- **Diff de tres vías o merge**: no hay consumidor que lo pida (D1).
- **Formatos binarios o diff estructurado de AST**: texto y JSON plano; lo demás cuando
  dos consumidores lo necesiten (D12).

## 4. Criterio de aceptación del contrato (semana 19)

- [x] `diff_records` campo a campo con volátiles ignorados y listados.
- [x] `diff_text` en hunks `cambiada/agregada/eliminada` con líneas y posiciones.
- [x] `text_similarity` en [0, 1], determinista.
- [x] Primer consumidor real: `cassette-diff` (sem. 19) — deriva del modelo entre dos
      grabaciones del mismo prompt, narrada con LLM validado.
