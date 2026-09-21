# Changelog

La versión es la del paquete `llm-dev-core`. El historial comienza con **v1.0 (semana 13)** — hasta entonces el core es `0.x` y puede romperse sin aviso (D3).

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