# Changelog

## v1.3.0 — 2026-11-20 (semana 21, C13)

- **`agent-loop` (C13, ADR-11): el loop mínimo con puerta humana.** Proponer
  (cerebro inyectado), confirmar (`confirm` antes de cada efecto), ejecutar
  (herramientas con nombre), registrar (trace auditable). El error de una herramienta
  no mata la corrida; el rechazo termina sin insistir; el presupuesto de pasos es
  visible (`paro="presupuesto"`), no un timeout.
- La hoja no cambia: `agent-loop` no depende de ningún módulo del core ni llama
  modelos — como `bot-base`, el determinismo es por construcción (D4) y el cerebro
  (un cierre sobre `LlmClient`, o un guion en tests) se compone en el consumidor.
- Primer consumidor: `checklist-walker` (sem. 21), que camina un checklist sobre un
  repo real con herramientas de lectura (`exists/read/grep`) y reporta con LLM
  validado.
- 172 tests en el core (165 + 7 de agent-loop).

## v1.2.0 — 2026-11-20 (semana 19, C12)

- **`diff-engine` (C12, ADR-10): comparación estructural determinista.** Nace vencida
  (su seed estaba calendariado en la sem. 19 junto a la verificación que pagó esa
  semana) y con su primer consumidor: `cassette-diff`, que mide la **deriva del
  modelo** entre dos grabaciones del mismo prompt con la misma entrada (demo real:
  similitud 0.6283, un hunk, `drift_menor`).
- Contrato del módulo (ADR-10): `diff_records` campo a campo con **volátiles
  declarados y listados** (timestamp, ids y latencias no son deriva; esconder que se
  ignoran, sí sería mentir), `diff_text` en hunks `cambiada/agregada/eliminada`,
  `text_similarity` en [0, 1]. Determinista por construcción (difflib, D4); la hoja
  no cambia: stdlib + pydantic, sin dependencias del core.
- Qué NO es: similitud semántica — eso es `vector-core` (C11), que **sigue vencida
  desde la sem. 16** (deuda registrada en el issue #2).
- 165 tests en el core (157 + 8 de diff-engine).

La versión es la del paquete `llm-dev-core`. El historial arranca con el **hito v1.0 (semana 13)**: hasta 0.10.0 el core era `0.x` y podía romperse sin aviso (D3); desde v1.0.0 los contratos son estables.

## v1.1.1 — 2026-11-19 (semana 15, issue #1)

- **cache-ratelimit: la poda del `CachedProvider` es amortizada.** `_prune` escaneaba
  todo el store en cada `complete()` (issue #1): el hit costaba 1.8 µs con una entrada
  y 45 µs con 2 500 (ratio 25×). Ahora la poda corre a lo sumo una vez por ventana de
  `ttl/2` y el coste del hit deja de crecer con el tamaño del store: **ratio 1.0×**
  medido por `make verify-perf` — la cláusula `cache_hit_scaling` pasa a `TRUE` y el
  baseline de rendimiento queda en **7 `TRUE`, 0 `FALSE`**.
- Sin cambio de contrato observable: una entrada vencida nunca se devuelve (la
  frescura siempre se comprueba por entrada); solo puede quedar en memoria hasta la
  próxima poda (~1.5×`ttl`). ADR-7 §2 queda enmendado con la decisión y su medición,
  sin tocar la línea del ancla preexistente.
- El test de poda existente sigue verde sin editar; uno nuevo fija la cadencia
  (ventana cerrada ⇒ no poda) y la frescura por entrada (vencida pedida ⇒ miss fresco).
- 157 tests en el core, 79 en los 12 consumidores — todos verdes contra el core
  modificado, `check_consumers` OK ×12.

## v1.1 — 2026-11-19 (verificación objetiva, semana 14, F0-F4)

- **F0: baseline de verificación medible.** `scripts/verification_baseline.py` mide nueve
  cláusulas contractuales contra artefactos reales y escribe `docs/verification/baseline.json`
  más `docs/verification/BASELINE.md` (`make verify-baseline`). Ninguna cifra del informe está
  escrita a mano: el veredicto se deriva de la medición.
  Resultado inicial: 4 `TRUE`, 2 `PARCIAL`, 3 `FALSE`.
- **F1: prueba de sensibilidad.** `scripts/verification_sensitivity.py` inyecta nueve
  rupturas deliberadas (parse no determinista, body desplazado, validador permisivo,
  detector que marca todo, `Schedule` siempre dispuesto, `Span` con 19 campos, …) y exige
  que la medición correspondiente cambie. Las nueve se detectan; si alguna dejara de
  detectarse, el script sale 1.
- **F2: los tres defectos de código quedan pagos** (el baseline pasó de 4 `TRUE` a 7):
  - `parser-io`: una sección Markdown sin cuerpo ya no desaparece en silencio. Se conserva
    con `body == ""`, `body_tokens == 0` y `line_end == line_start`.
  - `parser-io`: la ruta H1-fallback (documento sin H2) ahora respeta el mismo contrato de
    líneas que la ruta H2 — `body == lines[line_start:line_end]` en el **100%** de las
    secciones del corpus real (187/187, antes 184/186). El texto del heading ya no se
    duplica dentro de `body` y el frontmatter de los prompts tampoco.
  - `secure-base`: el detector `phone` exige forma escrita (`+`, paréntesis o separador).
    Dejaba de marcar `uuid` y `epoch` como teléfono (2 de 10 negativos duros). El coste
    asumido y documentado: un teléfono de 10 dígitos sin separador ya no se marca.
  - ADR-3 §2 y ADR-9 §2 quedan actualizados con el contrato corregido y su oráculo.
- Sin cambios rompientes para los consumidores: los 12 repos siguen verdes contra el core
  modificado y `check_consumers` da OK en los 12.

### F2.1 — el cierre del cierre

Un cuestionamiento del propio F2 encontró cuatro huecos. Todos están pagos:

- **Las cláusulas ya no son del instrumento.** `scripts/verification_clauses.py` registra,
  por medición, el archivo y la línea del contrato que se cita, y su tipo lo decide
  `git show v1.0.0:<archivo>` — no el autor. Resultado: 4 cláusulas `PREEXISTENTE`
  (campos del span, tres formas de JSON, determinismo D4, TTL/ráfaga/idempotencia),
  3 `DECISION v1.1` (contrato de líneas, heading sin cuerpo, forma escrita de `phone`)
  y 2 `CRITERIO DE PROYECTO`, que viven ahora en `docs/verification/METODOLOGIA.md`.
  Verificar una decisión de v1.1 no dice nada sobre el pasado: el informe lo dice.
- **Cita falsa corregida.** El baseline citaba "ADR-1 §10" para los campos del span; §10
  no existe (son §1–§6) y la lista está en la línea 58. La medición ya no hardcodea 20:
  parsea esa lista del ADR y compara conjuntos, así que un campo nuevo o borrado se ve sin
  editar el script.
- **La autorreferencia de F0 queda escrita en el artefacto**, no solo en la conversación:
  `BASELINE.md` incluye una sección *Historial de cláusulas* que admite que el `FALSE` de
  F0 en `empty_heading` se apoyaba en una cláusula inventada.
- **El trade-off de `phone` tiene ancla ejecutable.** `sec-check/tests/test_tradeoff.py`
  fija las dos direcciones: `+57 300 123 4567` se redacta y `assert_redacted` lo ve;
  `3001234567` sin separador pasa limpio, y el test lo declara hueco conocido.
- **El sentinel `line_start == 0` lo cubre el consumidor.** `content-ray/src/content_ray/main.py`
  renderiza `max(1, line_start)` para no imprimir `L0`, y tres tests nuevos fijan el panel,
  el lookup de `--sample doc:1` y que los documentos con heading no cambian de rango.
- Sensibilidad: la ruptura de `span_contract` pasó de "19 vs 20" a "falta `cost_usd`",
  que es el fallo real ahora que el número sale del ADR.
- 134 tests en el core (107 de v1.0), 78 en los 12 consumidores, `check_consumers` OK ×12.

### F3 — los dos `FALSE` restantes, y por qué eran del instrumento

Los dos `FALSE` de F2 no eran datos malos: eran criterios malos, y ninguno de los dos
podía volverse `TRUE` nunca. El baseline queda en **9 `TRUE`, 0 `PARCIAL`, 0 `FALSE`**.

- **`cost_usd` devolvía 0 para todo.** La tabla de precios tiene una sola entrada,
  `big-pickle`, pero los cassettes registran `opencode/big-pickle`: el nombre no
  coincidía, la búsqueda fallaba y caía al `(0.0, 0.0)` por defecto. Peor: ese
  defecto silenciaba el caso grave — un modelo de pago sin pricedar reportaba $0 y
  el cap de costo nunca disparaba. `llm_client.pricing` gana `price_key()` (resuelve
  el prefijo de proveedor) y `model_price_known()`, que separa "gratis" de
  "desconocido". El criterio de F0 (`$0.0000` en la página ⇒ `FALSE`) declaraba roto
  un dato correcto: para `big-pickle` el 0 **sí** estaba medido.
- **La página de evidencia separa los tres ceros que confundía.** Antes mostraba
  `$0.0000` en las doce filas sin decir de dónde salía. Ahora separa `llamadas (span)`
  de `llamadas (cassette)`, publica tokens in/out, y rotula cada costo:
  `(spans)`, `(cassette · modelo en tabla de precios)`, `costo desconocido` o
  `sin datos de llamada`. Un cassette no es un span: trae `usage` real del proveedor
  pero no pasó por el pipeline del core, así que no tiene `latency_ms` ni
  `retry_count` y no se suma en un único "llamadas". Resultado: 40 llamadas y
  190 004 / 12 393 tokens que antes no aparecían en ninguna parte.
- **`evidence-api` y `fleet-bot` rotulan el costo** con la misma regla, y sus README
  se actualizaron con la salida real (12 consumidores, no 10).
- **`docs_claims` ya no depende de una constante.** F0 fijaba
  `verificado_por_ejecucion: 0` escrito a mano, así que el veredicto no dependía de
  nada medido. Ahora la cifra se clasifica antes de exigirle una ejecución: de las
  98 de los 12 READMEs, 12 son claims de contrato y 12 coinciden con su oráculo;
  las otras 86 son puertos, códigos HTTP, fechas, porcentajes, transcripciones o
  números de semana, que no afirman nada sobre el comportamiento del sistema.
- **Dos README tenían cifras falsas** y el oráculo las cazó: `content-ray` decía
  "12 ADRs" cuando hay 10, y `core-smoke` decía "107 tests" cuando ya no eran 107.
  La segunda no se corrige poniéndole el número nuevo: se sustituye por el comando,
  porque un conteo de tests envejece igual de rápido. La metodología dice ahora que
  una cifra de contrato que depende de un número cambiante se escribe como comando.
- **Las rupturas de F1 seguían mintiendo.** `evidence_self_audit` y `docs_claims`
  fijaban claves que la medición reescrita ya no usaba, así que "pasaban" sin
  comprobar nada. Ahora el harness nombra cada ruptura por la medición que rompe
  (`idempotence`, no `parse_determinism`) y un test exige que toda medición tenga la
  suya y que siga detectándola. La de `evidence_self_audit` cambió de sentido: ahora
  rompe con un modelo fuera de la tabla de precios, que es el fallo real.
- ADR-6 §2 registra el cambio de contrato: "de cada fuente que falte, cuenta cero"
  sigue valiendo para el conteo y era falsa para la interpretación.
- 152 tests en el core, 78 en los 12 consumidores, `check_consumers` OK ×12,
  sensibilidad 10/10.

### F4 — "optimizado" gana oráculo: la forma es contrato, el número no

La pregunta "¿está optimizado?" no tenía respuesta verificable: §4 del baseline
excluía la calidad y ninguna cifra medía velocidad. `scripts/verification_perf.py`
(`make verify-perf`) abre esa dimensión bajo tres reglas nuevas
(`docs/verification/METODOLOGIA.md` §7):

1. **Un tiempo absoluto no es contrato** (depende del hardware): lo verificable es
   la forma — el coste de una operación O(1) no crece con el estado.
2. **Pisos de guardarrail ~100× por debajo de lo medido** para seis operaciones del
   camino caliente (parser, detectores, validación, span, precio, rate-limit): solo
   una regresión estructural los rompe.
3. **La deuda visible vale más que el verde fingido**: un `FALSE` crónico se publica
   con su acción abierta.

Resultado inicial: **6 `TRUE`, 1 `FALSE`**. El `FALSE` es `cache_hit_scaling`: el
coste de un hit de `CachedProvider` crece con el tamaño del store (1.8 µs con 1
entrada vs ~45 µs con 2 500; ratio ~25×, umbral 10×) porque `_prune` escanea todo el
diccionario en cada `complete()`. Fix registrado en el issue #1 (sem. 15); ningún
contrato del baseline se rompe por eso.

- Siete cláusulas nuevas en `scripts/verification_clauses.py`, todas
  `CRITERIO DE PROYECTO` ancladas a §7 (el tag v1.0.0 no contiene esas líneas).
- El test del registro de cláusulas pasa de igualdad exacta a subconjunto: el
  registro ya tiene dos familias (contratos y perf) y cada una exige la suya.
- `docs/verification/{perf.json,PERF.md}` se escriben en cada corrida; el JSON de
  perf no es sync-testeable (los tiempos varían), así que la suite exige estructura,
  veredictos derivados de la medición y anclas — no cifras congeladas.
- 156 tests en el core (152 de F3 + 4 de perf), baseline regenerado con el corpus
  ampliado (su corpus incluye los scripts y tests nuevos, como manda su contrato).

## v1.0 — 2026-10-08 (hito v1.0, semana 13)

- **Primer semver mayor: los contratos pasan a estables.** Diez módulos (ADR-0 a
  ADR-9) con criterios de aceptación escritos y doce consumidores reales detrás.
  Sin cambios rompientes previstos desde 0.10.0; a partir de aquí, deprecación
  explícita antes que sorpresa (D3 deja de aplicar "puede romperse sin aviso").
- No hay módulos nuevos: la semana 13 es de consolidación (D10). El bump es de
  *estabilidad*, no de superficie.
- Décimo consumidor: `binahco/evidence-api` (sem. 11) — el dashboard vivo de la
  flota sobre `web-api-base`: `GET /evidence` sirve la página de evidencia (§10.1)
  en vivo con `ci-pack.metrics` (sin `make validate`), `GET /fleet/status` expone
  la matriz por-repo y `GET /fleet/digest` da el veredicto LLM validado
  (`fleet-digest-generator` → `fleet-digest-v1`, caché TTL diaria). Composición
  70/30: reutiliza siete módulos, cero módulos nuevos.
- Undécimo consumidor: `binahco/docs-gen` (sem. 12) — sitio de documentación desde
  los ADRs del core: `parser-io` normaliza cada ADR y el cuerpo de las páginas sale
  **sin LLM**; la narrativa (tagline + blurb por ADR) es la única salida de modelo,
  validada contra `site-digest-v1` (`site-digest-generator`). Render determinista.
- Duodécimo consumidor: `binahco/core-smoke` (sem. 13) — smoke de publicación:
  importa los diez paquetes públicos del core desde la distribución publicada y
  falla si alguno no carga o la versión no es 1.x, más veredicto LLM validado
  (`core-health-generator` → `core-health-v1`). Es el consumidor que **verifica el
  v1.0.0 publicado** en vez de dogfoodear el árbol de trabajo.
- La flota sigue en `llm-dev-core ^0.x` (semanas 2–12): el v1.0 se publica sin
  obligar a los consumidores existentes a migrar; los nuevos pueden pedir `^1.0`
  (como hace `core-smoke`). La matriz repo × versión queda mixta a propósito.

## v0.10 — 2026-10-01 (parser-io seed)

- Semana 10: nace `packages/parser-io` v0.1.0 dentro de un consumidor real
  (`content-ray`).
  - Contrato ADR-9: la **capa de lectura de archivos** que piden `docs-gen`
    (sem. 12), `vector-core` (sem. 16), `diff-engine` (sem. 19) y `scraper`
    (sem. 28). `parse(source, text?, fmt?)` normaliza `markdown`/`csv`/`json`
    a un `ParsedDocument` determinista: secciones con anchor y `line_start`/
    `line_end`, tablas con cabeceras y línea, `approx_tokens` para ventanas.
    `ParseError` tipado con `source` + `line`; `iter_documents` sorted.
  - Hoja: pydantic + stdlib, no importa `llm-client` (el sanitizado y el LLM se
    componen en el consumidor, como ADR-7/8). El conteo real de tokens (no la
    heurística) es de `vector-core`.
- Noveno consumidor: `binahco/content-ray` (sem. 10) — escanea los `.md` de
  `llm-dev-core` (dogfood real), ventanas por sección y digest LLM validado
  (`content-scan-generator` → `content-summary-v1`); compone `secure-base`
  (sanitizar antes del prompt) y `cache-ratelimit` (TTL por archivo). Nace
  evaluado y con CI determinista.
- La flota se mantiene en `llm-dev-core ^0.9` (parser-io es aditivo): la matriz
  repo × versión queda mixta hasta el v1.0 (sem. 13) — decisión de la sem. 10.
- Wheel unificado (D1): `llm-dev-core 0.10.0` añade `parser_io` top-level.
  `make validate` en verde; evidencia a 9 consumidores.

## v0.9 — 2026-09-30 (bot-base seed)

- Semana 9: nace `packages/bot-base` v0.1.0 dentro de un consumidor real
  (`fleet-bot`).
  - Contrato ADR-8: la **recurrencia programada determinista** de la flota
    (eval-smoke diario, evidencia, resúmenes) formalizada: `Schedule` (intervalo
    monótono o predicado de calendario, reloj inyectable), `RunStore`
    (`JsonRunStore` atómico) para idempotencia por última corrida, `Task` +
    `run_tasks` (fallos capturados en `Digest`, nada se corta en silencio).
  - Hoja mantiene la vida: `bot-base` no depende de `llm-client` ni de otro módulo
    (pydantic + stdlib); la tarea LLM es composición del consumidor, como en ADR-7.
- Robustez de la flota (deuda de la sem. 8): detectores `phone`/`credit_card` de
  `secure-base` ignoran literales float (`0.6666…` dejó de sonar a tarjeta/teléfono).
- Los 8 consumidores pasan a depender de `llm-dev-core ^0.9` (locks y workflows
  `eval-smoke.yml` regenerados con `core_ref=v0.9.0`); CIs deterministas sobre
  cassettes (D4), `ci-scribe audit` verde en los 8 sin hacks.

## v0.8 — 2026-09-23 (cache-ratelimit seed)

- Semana 8: nace `packages/cache-ratelimit` v0.1.0 dentro de un consumidor real
  (`llm-gateway`).
  - Contrato ADR-7: la caché y el ritmo son *política de composición*, no de la hoja.
    `RateLimiter` (token bucket `rpm`/`burst`, reloj inyectable para D4),
    `ThrottledProvider` y `CachedProvider` (TTL + poda; streams sin cachear) implementan
    `llm_client.provider.Provider` y se enchufan donde vive cualquier provider:
    `LlmClient(ThrottledProvider(CachedProvider(inner), RateLimiter(rpm=60)))`.
  - Séptimo consumidor: `Proyectos/llm-gateway` (sem. 8) — proxy HTTP sobre
    `web-api-base`: `POST /llm` con la cadena cache+throttle, `GET /gateway/stats`
    (bucket + hits/miss) y cabecera `X-Cache`; nace evaluado y con CI determinista.
- **Excedente sem 7 (regla 5):** `ci_pack.jobs` ya no envuelve el `git clone` en
  continuaciones YAML (`width=400`); test nuevo.
- Decisión: `cache-ratelimit` depende solo de `llm-dev-client` (protocolo `Provider`);
  los `429` de ritmo son de la capa HTTP (web-api-base), distintos del `429
  presupuesto_excedido`.
- Wheel unificado (D1): `llm-dev-core 0.8.0` empaqueta `llm_client` + `schema_validate`
  + `secure_base` + `test_kit` + `web_api_base` + `ci_pack` + `cache_ratelimit`
  top-level. `make validate` en verde; 80 tests.

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