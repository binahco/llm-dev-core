# ADR-0 — Stack único: Python 3.12+

- **Fecha:** 2026-09-20
- **Estado:** aceptada
- **Origen:** D11 en `ARCHITECTURE.md` (la ADR-0 del proyecto)

## Contexto

El core tendrá módulos de cliente LLM, validación de esquemas, evals, CI, observabilidad y más. Mantener dos runtimes principales en el core significa duplicar cada pieza: cliente, validación, evals, packaging, errores y documentación. El bilingüismo accidental es una deuda que el proyecto no necesita.

El ecosistema LLM tiene su centro de gravedad en Python: las SDKs de los proveedores, las librerías de observabilidad y la práctica de evals están maduras en él. Pydantic modela con precisión el invariante central del proyecto (la salida de un LLM es input no confiable), y el tooling para publicar un paquete versionado en PyPI es trivial.

## Decisión

El core se construye sobre un único runtime principal:

- **Python 3.12+**
- **Pydantic** para validación (incl. `schema-validate`)
- **FastAPI** para APIs (`web-api-base`)
- **pytest** para tests (`test-kit`)
- **uv** para tooling y publicación
- **Logging estructurado** (JSON) para observabilidad (`cost-obs`)

Los consumidores pueden tener frontends u otros componentes en cualquier otra tecnología. Toda lógica LLM, validación, prompts, evals y observabilidad pasa por el core en el stack oficial.

## Consecuencias

- **Positivas:** una sola cultura de código, una sola guía de estilo, evals y CI compartidos sin traducción.
- **Negativas:** quien quiera usar el core desde otro runtime (TS, etc.) queda fuera. Es el precio de no mantener dos ecosistemas; se acepta.
- El contrato de `llm-client` (ADR-1) y las plantillas se escriben ya en este stack.