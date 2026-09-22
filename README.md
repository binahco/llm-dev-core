# llm-dev-core

> La abstracción que solo se usa una vez es una hipótesis; la que se usa treinta, un diseño.

Núcleo versionado y publicado del que dependen 52 proyectos en 52 semanas: un solo sistema acumulativo, no 52 demos desconectadas.

Toda llamada a un LLM pasa por `llm-client`, toda salida no confiable pasa por `schema-validate`, todo prompt vive en `prompt-registry`. Ver `ARCHITECTURE.md` para la tesis, las decisiones (D1–D12) y las métricas verificables.

- **Estado:** v0.6 · Semana 6
- **Stack:** Python 3.12+ (ADR-0, `docs/decisions/0000-stack.md`)
- **Estructura:** `packages/` (módulos), `templates/` (consumidor clonable), `scripts/` (verificación), `docs/`
- **Empaquetado:** una sola dist `llm-dev-core` (D1): `llm_client`, `schema_validate`, `secure_base`, `test_kit` y `web_api_base` top-level; los consumidores dependen de `llm-dev-core ^0.x`, nunca de módulos sueltos.

## Desarrollo

```bash
uv sync        # instala el workspace
make validate  # invariantes: estructura, plantillas, ADR-0, sintaxis
uv run pytest  # tests (59 a la fecha)
```