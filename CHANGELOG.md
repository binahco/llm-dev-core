# Changelog

La versión es la del paquete `llm-dev-core`. El historial comienza con **v1.0 (semana 13)** — hasta entonces el core es `0.x` y puede romperse sin aviso (D3).

## v0.7 — 2026-09-23 (ci-pack seed)

- Semana 7: nace `packages/ci-pack` v0.1.0 dentro de un consumidor real (`ci-scribe`).
  - Contrato ADR-6: tres piezas. `lints`: `run_lints`/`lint_imports` (SDKs directos),
    `lint_inline_prompts` (prompts pegados en código) y `lint_secrets` (vía `secure-base`
    `assert_redacted`); salta tooling/cachés/tests/scripts y audita lo que cruza al proveedor
    (cassettes, prompts, evals, src). `metrics`: `collect` lee `core-consumer.yml` + spans de
    `llm-client` y `render` produce la página de evidencia (§10.1). `jobs`:
    `render_eval_smoke_job(core_ref=...)` genera el `eval-smoke.yml` (el mismo layout local:
    `git clone` del core en `../llm-dev-core`, `uv sync --frozen`, replay determinista).
  - Sixth consumidor: `Proyectos/ci-scribe` (sem. 7) — fleet ops: CLI `eval`/`audit`/`evidence`
    + Web API sobre `web-api-base` (`POST /fleet/audit` y `POST /fleet/triage`); el prompt
    `eval-triage-generator` nace evaluado (3 casos, cassette real, replay determinista).
    Dogfood: `audit` deserta la flota y `evidence` regenera la página; el `eval-smoke.yml`
    de sus 6 consumidores sale ya de `ci_pack.jobs`.
- **Auditoría de flota (sem. 7):** `ci-pack.lints` sobre los 5 consumidores previos desembocó en:
  - detector `bearer` de `secure-base` endurecido (exige token real ≥8 chars; antes casaba
    palabras como "Bearer en" → falso positivo);
  - fixtures de credenciales de `sec-check` hechas capturables por los detectores y su cassette
    re-grabado (3/3), sin `user:pass` ni claves sueltas en la cinta;
  - deuda CI de `bench-runner` (sem. 5) cerrada: `eval-smoke.yml` generado y en verde;
  - los 4 workflows previos regenerados por `ci_pack.jobs` manteniendo su `core_ref` coincidente
    con el `uv.lock` de cada consumidor.
- Decisión: `ci_pack` no importa `test-kit` ni `web-api-base`; depende de `llm-client` (schema
  de spans) y `secure-base` (máscara). PyYAML entra al wheel unificado (D1).
- Wheel unificado (D1): `llm-dev-core 0.7.0` empaqueta `llm_client` + `schema_validate` +
  `secure_base` + `test_kit` + `web_api_base` + `ci_pack` top-level. `make validate` en verde
  y regenera `docs/metrics/evidence.html`; 66 tests.

## v0.6 — 2026-09-22 (web-api-base seed + retrofit #0)

- Semana 6: nace `packages/web-api-base` v0.1.0 dentro de un consumidor real (`eval-api`).
  - Contrato ADR-5: Swift FastAPI LLM-ready — `create_app(title, version, *, client)` expone
    `GET /health`, `POST /llm` (pipeline completo de `llm-client` con la validez como gate) y
    errores uniformes: 429 `presupuesto_excedido`, 422 `salida_no_validada`/`peticion_invalida`,
    502 `proveedor_indisponible`, 500 `error_interno`. `llm_complete`/`sse_response` para reuso.
  - Composición, no acoplamiento: la base recibe el `client` ya cableado por el consumidor
    (renderer/validator/emitter) y **no** importa `test-kit` (la evaluación es composición, no capacidad).
- Quinto consumidor: `Proyectos/eval-api` (sem. 6) — "bench-runner como servicio": `POST /evals/run`
  (test-kit por HTTP con umbral; 422 `dataset_invalido`) y `POST /summarize` (prompt
  `eval-summarizer`, schema `eval-summary-v1`, gate del core). Dogfood: el resumidor nace evaluado
  (3 casos, cassette real grabado, replay determinista).
- **Retrofit #0 (sem. 6):** los prompts de los consumidores 2–4 salen del seed de 1 caso y pasan a
  datasets congelados reales (3 casos cada uno) + cassettes grabados + CI `eval-smoke.yml`:
  - `commit-cli`: el prompt detectado como bug — pedía "la lengua de los mensajes previos" sin
    recibirlos (el modelo intentaba `git log`). Prompt v0.2.0 con `language` explícito.
  - `release-scribe` y `sec-check`: datasets 3 casos + replay determinista en CI.
  - Issues de retrofit creados en los 3 repos (label `retrofit`).
- Decisión: FastAPI (y starlette) entran como dependencia obligatoria del wheel unificado (D1) —
  documentado en ADR-5; lo mismo que ya hizo sem 1 con httpx/pydantic.
- Cosmética: notas "ci-pack (sem. 6)" corregidas a sem. 7 en `scripts/` (el calendario manda).
- Wheel unificado (D1): `llm-dev-core 0.6.0` empaqueta `llm_client` + `schema_validate` +
  `secure_base` + `test_kit` + `web_api_base` top-level. `make validate` en verde; 59 tests.

## v0.5 — 2026-09-22 (test-kit seed)

- Semana 5: nace `packages/test-kit` v0.1.0 dentro de un consumidor real (`bench-runner`).
  - Contrato ADR-4: los tests de un prompt son datasets — `EvalDataset.from_jsonl` con casos
    `{prompt_id, prompt_version, input, expected, criteria}`; a partir de v0.5 un fichero inexistente
    se reporta como `DatasetError` (exit 2), no como traceback.
  - Tres criterios deterministas: `deterministic_match` (colapsa espacios, opción `ignore_case`),
    `json_match` (JSON con/sin caretas) y `schema_match` (estructura validada vía `schema-validate`,
    `expected` opcional).
  - Runner agnóstico del transporte: el consumidor inyecta `judge: EvalCase → CompletionResult`; el
    runner suma `pass_rate`, compara contra `threshold` y acumula `cost_usd`. Modos `smoke`/`full` (§8.1).
- Cuarto consumidor: `Proyectos/bench-runner` (sem. 5) — CLI `bench-runner` que evalúa prompts contra
  datasets congelados (exit 0 verde, 1 regresión, 2 dataset inválido). Su propio prompt
  `regression-report-generator` (triaje de regresión, `modo json` para reportes estructurados y
  `modo texto` para veredicto en línea) nace evaluado: dogfood del seed. 4 casos, cassette real
  grabado, replay determinista en CI (D4) que hasta reproduce la reparación grabada.
- `schema-validate`: el hook `validator` respeta el contrato `schema=None → ok` (necesario para que
  `modo texto` no fuerce reparaciones JSON al validar salidas sin schema).
- Regla nueva en vigor desde la sem. 5: todo prompt nuevo del core/consumidores debe tener evaluación
  (frontmatter `eval` + dataset no vacío), enforced por `make validate-consumer`.
- Wheel unificado (D1): `llm-dev-core 0.5.0` empaqueta `llm_client` + `schema_validate` + `secure_base`
  + `test_kit` top-level. `make validate` y `validate-consumer` (4 consumidores) en verde; 49 tests.

## v0.4 — 2026-09-22 (secure-base seed)

- Semana 4: nace `packages/secure-base` v0.1.0 dentro de un consumidor real (`sec-check`).
  - Contrato ADR-3: `detect`/`redact`/`sanitize_for_prompt`/`assert_redacted` + `SecurityProfile` (declaración
    de tipos para el lint anti-secretos de `ci-pack`, sem. 7).
  - Máscara unidireccional y determinista: placeholder `[REDACTED:<tipo>:<n>]`; `Finding.match` es preview
    truncado (24 chars), nunca el secreto completo. 9 detectores (email, phone, ipv4, credit_card, aws_access_key,
    github_token, private_key, bearer, url_userinfo).
  - `secure-base` es hoja (no depende de `llm-client` ni de `schema-validate`); se compone en el renderer del
    consumidor, antes de que el texto cruce al proveedor.
- Tercer consumidor: `Proyectos/sec-check` (sem. 4) — escáner de secretos con triaje LLM: detecta en `git diff`
  o archivo, redacta con `secure-base`, aborta si `assert_redacted` no es vacío, y solo el texto enmascarado viaja
  al LLM (`opencode` local o replay). Reporte `sec-findings-v1` validado con `schema-validate`; exit 0 sin secretos,
  1 con secretos, 2 inválido. Tape real grabado con 3 hallazgos críticos, replay en verde.
- Wheel unificado (D1): `llm-dev-core 0.4.0` ahora empaqueta `llm_client` + `schema_validate` + `secure_base`
  top-level. `make validate` y `validate-consumer` (3 consumidores) en verde; 37 tests.
- Publicado `llm-dev-core 0.4.0` en PyPI (trusted publishing, tag `v0.4.0`).
- Nota del cómo: el primer tag `v0.4.0` se creó antes del bump de versión en `pyproject.toml`, así que la
  primera ejecución de `publish.yml` subió el wheel `0.3.0` ya existente (409 en PyPI). Se corrigió bumping
  a `0.4.0` y reconstruyendo el tag sobre ese commit (queda un run fallido en Actions y un mensaje de commit
  de "0.4" que no incluía el bump; el estado final es correcto). Lección: el tag de publicación se crea
  **después** de confirmar la versión en `pyproject.toml`.

## v0.3 — 2026-09-21 (schema-validate seed + dist unificada)

- Semana 3: nace `packages/schema-validate` v0.1.0 dentro de un consumidor real (`release-scribe`).
  - Contrato ADR-2: validación Pydantic de la salida LLM (JSON con/sin caretas, errores campo a campo),
    registro `SchemaId → modelo`, `parsed` poblando `CompletionResult.parsed`.
  - Reparación: el lazo/presupuesto/cap sigue en `llm-client` (hoja); `schema-validate` alimenta los
    errores vía el hook `validator`. Ajuste menor ADR-1: `ValidationResult.parsed`.
  - Tape real grabado de `opencode run` sin API key (replica validada con `parsed`).
- **Empaquetado unificado (D1):** el core pasa a publicarse como una sola dist `llm-dev-core` (0.3.0)
  con `llm_client` y `schema_validate` top-level; los consumidores dependen de `llm-dev-core ^0.3`, nunca
  de módulos sueltos. `commit-cli` migra a la dist unificada.
- Segundo consumidor: `Proyectos/release-scribe` (sem. 3) — release notes JSON validadas desde `git log`;
  reutiliza `llm-client` + `schema-validate`.
- Calendario armonizado (§5 vs. §10): `schema-validate` (3), `secure-base` (4), `test-kit` (5),
  `web-api-base` (6), `ci-pack` (7), `cache-ratelimit` (8), `bot-base` (9), … hasta `cost-obs` (39).
  Deuda aprobada en el review: la sem-2 quería publicar ya en PyPI; al unificar el empaquetado, la primera
  publicación real pasa a ser esta v0.3.
- Publicado `llm-dev-core 0.3.0` en PyPI (trusted publishing OIDC, workflow `publish.yml` en tags `v*`):
  primera release real del core; instalable y verificado desde el registro (D1).

## v0.2 — 2026-09-20 (llm-client seed)

- Semana 2: nace `packages/llm-client` v0.1.0 dentro de un consumidor real (`commit-cli`).
  - Contrato ADR-1 aceptada: `complete`/`stream`, retry+backoff+jitter, reparación con tope, cap de costo, cache, span de 20 campos.
  - Record/replay nativo: cassettes sin API key (`ReplayProvider`); tape real grabado con el transport `opencode` (sesión local, sin key).
  - Transportes: `opencode` (`opencode run --format json`) y `openai-compatible` (HTTP).
  - Workspace uv activado (`members = ["packages/*"]`); grupo dev de pytest. `make validate` ahora también corre los tests.
  - Primer consumidor: `Proyectos/commit-cli` (único módulo del core reutilizado a la fecha: `llm-client`). La métrica de reutilización real se medirá en §10.1 desde el corte de semanal.

## v0.1 — 2026-09-20 (seed)

- Semana 1: documento `ARCHITECTURE.md`, ADR-0 (stack Python 3.12+), contrato mínimo de `llm-client`, plantillas de consumidor.
- Enforcement base (§3): `scripts/check_consumers.py` implementado (modo `--self` y de consumidor), `make validate` y workflow `ci.yml`. Pendiente hasta sem. 6: lint anti-imports, evals en CI y página de evidencia (ci-pack).