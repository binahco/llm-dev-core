# llm-dev-core

> La abstracción que solo se usa una vez es una hipótesis; la que se usa treinta, un diseño.

Núcleo versionado y publicado del que dependen 52 proyectos en 52 semanas: un solo sistema acumulativo, no 52 demos desconectadas.

Toda llamada a un LLM pasa por `llm-client`, toda salida no confiable pasa por `schema-validate`, todo prompt vive en `prompt-registry`. Ver `ARCHITECTURE.md` para la tesis, las decisiones (D1–D12) y las métricas verificables.

- **Estado:** v0.8 · Semana 8
- **Stack:** Python 3.12+ (ADR-0, `docs/decisions/0000-stack.md`)
- **Estructura:** `packages/` (módulos), `templates/` (consumidor clonable), `scripts/` (verificación), `docs/`
- **Empaquetado:** una sola dist `llm-dev-core` (D1): `llm_client`, `schema_validate`, `secure_base`, `test_kit`, `web_api_base`, `ci_pack` y `cache_ratelimit` top-level; los consumidores dependen de `llm-dev-core ^0.x`, nunca de módulos sueltos.

## Qué es (y qué no es)

**Qué es:** una dist publicada (`llm-dev-core` ^0.x) que concentra el pipeline LLM de la
flota — llamadas, validación, seguridad, evals, web y caché/ritmo — sobre la que se montan
los consumidores. Cada módulo es una hipótesis que solo pasa a diseño si varios
consumidores la usan (la tesis del encabezado).

**Qué resuelve por sí solo:** lo común de 52 proyectos: el LLM se llama desde un solo
punto (`llm-client`), la salida no confiable no entra cruda (`schema-validate`), el
secreto no cruza al proveedor (`secure-base`), el CI de un consumidor se valida con
cassettes congelados (`test-kit` + `ci-pack`) y la web de un consumidor sale de una base
(`web-api-base`).

**Qué no es:** no es un framework ni un SDK público: los consumidores dependen de la dist
completa (D1), nunca de módulos sueltos, y su contrato es `core-consumer.yml` + la
cabecera de semana de cada README.

## Desarrollo

```bash
uv sync        # instala el workspace
make validate  # invariantes: estructura, plantillas, ADR-0, sintaxis + regenera docs/metrics/evidence.html
uv run pytest  # tests (82 a la fecha)
```