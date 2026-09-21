# llm-dev-core

> La abstracción que solo se usa una vez es una hipótesis; la que se usa treinta, un diseño.

Núcleo versionado y publicado del que dependen 52 proyectos en 52 semanas: un solo sistema acumulativo, no 52 demos desconectadas.

Toda llamada a un LLM pasa por `llm-client`, todo prompt vive en `prompt-registry`, toda salida no confiable pasa por `schema-validate`. Ver `ARCHITECTURE.md` para la tesis, las decisiones (D1–D12) y las métricas verificables.

- **Estado:** v0.1 (seed) · Semana 1
- **Stack:** Python 3.12+ (ADR-0, `docs/decisions/0000-stack.md`)
- **Estructura:** `packages/` (módulos), `templates/` (consumidor clonable), `scripts/` (verificación), `docs/`

## Desarrollo

```bash
uv sync        # instala el workspace
uv run pytest  # tests (aún ninguno hasta sem. 2)
```