# Changelog

La versión es la del paquete `llm-dev-core`. El historial comienza con **v1.0 (semana 13)** — hasta entonces el core es `0.x` y puede romperse sin aviso (D3).

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