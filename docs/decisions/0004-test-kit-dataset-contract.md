# Contrato mínimo — `test-kit`

- **Fecha:** 2026-09-22
- **Estado:** aceptada
- **Origen:** D7 (ARCHITECTURE.md), §8.1, ADR-1 §109
- **Implementada en:** semana 5 (`packages/test-kit` v0.1.0, nacida dentro de `bench-runner`)

Los tests de un sistema LLM no son assertions: son **datasets**. Este ADR fija el formato de dataset y el
motor de evaluación determinista que todos los consumidores usarán desde la semana 5.

## 1. Dataset: formato de archivo (JSONL)

```jsonl
{"prompt_id": "…", "prompt_version": "0.1.0", "input": {"…": "…"},
 "expected": <sólido esperado o texto>, "criteria": {"type": "…", "schema": "…", "note": "…"}}
```

- Una línea = un caso (`EvalCase`). Un archivo = un prompt (`EvalDataset.from_jsonl`).
- Todos los casos de un dataset comparten `prompt_id` y `prompt_version` (error si se mezclan).
- `input` son las variables que el renderer del consumidor formatea.
- `expected` depende del criterio (ver §2).
- Archivos viven en `evals/` del consumidor y se referencian desde el `frontmatter.eval` del prompt
  (ya exigido por `check_consumers.py`).

## 2. Criterios de evaluación (v0.1 — deterministas)

| type | `expected` | pasa si |
|---|---|---|
| `deterministic_match` | texto | la salida normalizada (espacios + opcional `ignore_case`) es idéntica |
| `json_match` | dict o list | el JSON parseado de la salida es `==` (con/sin fenced ```json```) |
| `schema_match` | dict (opcional) | la salida valida contra el schema (`schema:` en el criterio) **y** si hay `expected`, el objeto parseado coincide |

Los tres son puros: mismo input → mismo veredicto. Costo de ejecución ≈ 0 en CI porque corren sobre
cassettes de `ReplayProvider` (ADR-1, D4) — el build nunca golpea APIs vivas.

## 3. Runner y umbral (`test_kit.run`)

```python
run(dataset, judge, *, mode="smoke", threshold=1.0) -> EvalReport
```

- `judge: EvalCase -> CompletionResult` lo cablea el **consumidor** (LlmClient + su renderer + replay o record).
  El runner es agnóstico del transporte: no sabe si ejecuta replay o record.
- `mode`: `smoke` (diario, barato, dataset corto) vs `full` (releases, cambios de prompt/modelo). §8.1.
- `threshold`: fracción [0,1] de casos que deben pasar. `EvalReport.threshold_ok` rompe el CI si no se llega.
- `EvalReport` agrega: total/passed/pass_rate, `cost_usd` (suma de los resultados), y un caso por ítem.

## 4. Horizontalidad y dependencias

- `test-kit` depende de `llm-client` (para `CompletionResult`) y de `schema-validate` (para `extract_json`).
  **Jamás al revés** (ARCHITECTURE:214): el cliente no sabe qué es un dataset.
- La calibración (D7) NO está en este contrato: un criterio no determinista (LLM-as-judge) necesitaría
  ~20 casos de ground truth etiquetados a mano para detectar bias. Queda como hook futuro (`criterion.type`
  se extiende sin romper el resto); el `LLM_JUDGE` se documenta como pendiente, no se implementa esta semana.
- El *formato de cassette* que ADR-1 delega en test-kit es el que ya existe en `ReplayProvider`: este módulo
  no reimplementa el formato, lo consume.

## 5. Qué NO contrata

- No decide el umbral por proyecto (eso es del `core-consumer.yml`, quemado en CI por cada consumidor).
- No define qué prompt tiene dataset: `check_consumers.py` obliga que el `frontmatter.eval` exista (sem. 5+).
- No es un runner de CI: `ci-pack` (sem. 7) conectará `run()` a jobs. Aquí ya está el primitivo.

## 6. Criterios de aceptación (semana 5)

- [x] `EvalDataset.from_jsonl` valida JSON, rechaza casos mal formados y evita mezclar prompt_ids.
- [x] `deterministic_match` y `json_match` pasan con fenced JSON y normalización de espacios/caso.
- [x] `schema_match` valida contra un modelo del `SchemaRegistry` y reporta errores campo a campo.
- [x] `run` calcula pass_rate, `threshold_ok` y suma `cost_usd`; distingue `smoke`/`full`.
- [x] Primer consumidor real: `bench-runner` (sem. 5) — su propio prompt nace con dataset en `evals/` y tapas reales.
- [x] El dataset de `bench-runner` combina los tres criterios: `schema_match` + `json_match` + `deterministic_match`.