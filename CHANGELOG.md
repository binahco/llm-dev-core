# Changelog

La versión es la del paquete `llm-dev-core`. El historial comienza con **v1.0 (semana 13)** — hasta entonces el core es `0.x` y puede romperse sin aviso (D3).

## v0.1 — 2026-09-20 (seed)

- Semana 1: documento `ARCHITECTURE.md`, ADR-0 (stack Python 3.12+), contrato mínimo de `llm-client`, plantillas de consumidor.
- Enforcement base (§3): `scripts/check_consumers.py` implementado (modo `--self` y de consumidor), `make validate` y workflow `ci.yml`. Pendiente hasta sem. 6: lint anti-imports, evals en CI y página de evidencia (ci-pack).