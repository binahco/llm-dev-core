# Contrato mínimo — `ci-pack`

- **Fecha:** 2026-09-23
- **Estado:** aceptada
- **Origen:** §2.1, §3, §10.1 de `ARCHITECTURE.md` (lints prometidos y página de evidencia),
  ADR-3 (`secure-base` como motor del lint anti-secretos) y ADR-4 (`test-kit.run` a jobs).
- **Implementada en:** semana 7 (`packages/ci-pack` v0.1.0, nacida dentro de `ci-scribe`)

`ci-pack` es la caja de herramientas de CI/flota del core: convierte en verificables
los invariantes de §3 que `check_consumers.py` no cubre por coste bajo día 1, conecta
`test-kit` con los jobs de CI, y genera la página de evidencia (§10.1) en cada merge.

## 1. API conceptual

```python
# lints — reglas 1 y 2 de §3, y regla 1 de §3.1:
from ci_pack import run_lints, lint_imports, lint_inline_prompts, lint_secrets
report = run_lints([repo1, repo2])          # LintReport{violations: list[str]}; .ok

# jobs — conecta test-kit.run() a un workflow determinista (sin LLM, D4):
from ci_pack import render_eval_smoke_job
yaml_text = render_eval_smoke_job(core_ref="v0.7.0", test_command="uv run pytest tests/test_replay.py -q")

# evidencia — la página de §10.1:
from ci_pack import collect, render
report = collect([consumer_repos...], spans_dir=...)
html = render(report)                          # → docs/metrics/evidence.html
```

## 2. Reglas

- **Lints que viven aquí** (§2.1/§3):
  - *anti-imports*: importar un SDK de proveedor (`openai`, `anthropic`, …) fuera de
    `llm_client` es violación — regla 1 de §3.
  - *anti-prompts-inline*: literales largos con marcas de instrucción LLM en código →
    los prompts viven en `/prompts` con frontmatter — regla 2 de §3.
  - *anti-secretos*: `secure-base` es el motor (`assert_redacted`); ci-pack solo lo
    barre sobre código y prompts — regla 1 de §3.1.
- **El job `eval-smoke` congela el layout semanal:** como los consumidores declaran el
  core por path editable (`../llm-dev-core`), el job clona el tag exacto y corre
  `uv sync --frozen` + replay. Reproduce el patrón que el retrofit #0 de la sem. 6
  copiaba a mano.
- **`collect` lee fuentes de verdad, no promesas:** manifiestos `core-consumer.yml`
  (reutilización y matriz repo × core), `prompts/` con su `eval` existente (cobertura)
  y los spans de `llm-client` (costo y llamadas). De cada fuente que falte, cuenta cero.
- **Dependencias hojas:** `llm-dev-client` (solo para el schema de `Span`) y
  `llm-dev-secure-base`. No depende de `test-kit` (el job solo lo *invoca* por CLI).

## 3. Qué NO contrata este documento

- **`compat-last-5`** (D8, `scripts/compat_check.sh`): es un stub declarado y formalizado
  en la sem. 13, con `v1.0`. ci-pack no lo adelanta.
- El **esquema del span**: es contrato público de `llm-client` (D4); ci-pack lo *lee*.
- La **observabilidad agregada** (`cost-obs`, sem. 39): aquí solo se agrega costo a
  granularidad de repo, para la tabla de evidencia.

## 4. Criterio de aceptación del contrato (semana 7)

- [x] `run_lints` detecta: import directo de un SDK de proveedor, prompt-inline, y
      secreto en claro (vía `secure-base`); repo limpio → vacío.
- [x] `render_eval_smoke_job` produce YAML válido que clona el core `v0.7.0` y corre el
      replay; idéntico al patrón ya verde en los 4 consumidores de la sem. 6.
- [x] `collect`/`render` producen la página de evidencia (reutilización %, cobertura de
      evals, matriz repo × core, llamadas y costo acumulado desde los spans).
- [x] `scripts/collect_metrics.py` delega en `ci_pack` y `docs/metrics/evidence.html` se
      regenera en `make validate`.
- [x] Primer consumidor real: `ci-scribe` (sem. 7), que reusa `llm-client` +
      `schema-validate` + `test-kit` + `web-api-base` + `ci-pack` para auditar la flota
      y publicar la evidencia.