# Contrato mínimo — `schema-validate`

- **Fecha:** 2026-09-21
- **Estado:** aceptada
- **Origen:** D5 en `ARCHITECTURE.md`
- **Implementada en:** semana 3 (`packages/schema-validate` v0.1.0, nacida dentro de `release-scribe`)

Este documento es el contrato escrito contra el que se implementa la semana 3. Define la API de validación,
el registro de esquemas y la división de responsabilidades de la **reparación automática** con el lazo que ya
vive en `llm-client` (D5). Los nombres son orientativos; los contratos que se congelan son la forma de
`ValidationResult` (con `parsed`) y el seam del hook `validator`.

## 1. API conceptual

```python
# Validar texto crudo del LLM contra un modelo Pydantic.
def validate_text(model: type[BaseModel], text: str) -> ValidationResult: ...

# Servir un callable listo para el hook `validator` de llm-client.
registry = SchemaRegistry()
registry.register("release-notes-v1", ReleaseNotes)
validator = registry.make_validator("release-notes-v1")
```

`ValidationResult` es el contrato público de `llm-client` (ADR-1, §2) **ampliado en la semana 3** con un campo:

```text
parsed  Any | null   # objeto Pydantic validado; solo poblado cuando ok == true
```

El cambio es un ajuste menor del ADR-1 dentro de la ventana `0.x` ("todo puede romperse" hasta la semana 13).
`llm-client` propaga `parsed` a `CompletionResult.parsed` sin estado nuevo propio.

## 2. Comportamiento de validación

- **JSON mode no garantiza esquema**, solo formato: `validate_text` no confía en él.
- Se aceptan tres formas de respuesta: JSON puro, JSON dentro de caretas ```json … ```, o JSON
  precedido/seguido de prosa (se recorta al primer `{`/`[` y último `}`/`]`).
- Los errores de Pydantic se aplanan a una lista legible `"campo: motivo"` que alimenta la reparación.
- Un `ValidationResult` con `ok == false` **nunca** trae `parsed`.

## 3. División de la reparación (respeta la regla de la hoja)

`llm-client` es la hoja del grafo de dependencias (§5): no puede importar `schema-validate`. El lazo de
reparación (presupuesto de 2 intentos, cap de costo, re-prompt con errores) **se queda en `llm-client`**,
donde ya existía desde la semana 2. `schema-validate` aporta el otro lado:

- valida cada intento y devuelve los errores que el lazo re-inyecta al prompt,
- el hook `validator` (`(text, schema) -> ValidationResult`) es el seam por el que se compone en el consumidor,
- `span.repaired_attempts` y `span.status` (`repaired`/`failed`) ya lo registran los spans de `llm-client`.

El resultado: el orquestador y los topes no cambian; lo que se extrae es la fuente de verdad de "¿la salida
es confiable o no?", y su primer consumidor (`release-scribe`) la usa sin tocar el cliente.

## 4. Registro de esquemas (SchemaId)

`CompletionRequest.response_schema` es un **id** (`str`), no un objeto: el consumidor registra el id contra
un modelo Pydantic en su propia instancia de `SchemaRegistry` (o la `default_registry`). Un id no registrado
falla de forma ruidosa (`SchemaNotFound`): un prompt que declara un schema inexistente es un error de
configuración, no un "schema opcional".

## 5. Qué NO contrata este documento

- No define formatos de cassette (sem. 5, `test-kit`).
- No renderiza ni resuelve prompts (sem. 35, `prompt-registry` fase 2).
- No decide el orden del lazo de reparación ni sus topes: eso es de `llm-client` (D5).
- No es un validador de dataframes ni de salidas no-LLM: el criterio de admisión (§6 de `ARCHITECTURE.md`)
  lo acota a alimentar/consumir el pipeline LLM.

## 6. Criterio de aceptación del contrato (semana 3)

- [x] `validate_text` valida JSON con y sin caretas; errores legibles campo a campo.
- [x] `make_validator(schema_id)` enchufa en `LlmClient(validator=...)`; la reparación usa sus errores.
- [x] Una firma gestada (inválida → válida) termina con `status == "repaired"`, `repaired_attempts == 1` y `parsed` poblado.
- [x] Una firma siempre inválida agota el presupuesto (2) y termina `status == "failed"` con `error_type == "validation"`.
- [x] Se propaga `parsed` vía `ValidationResult` → `CompletionResult.parsed` (ajuste ADR-1).
- [x] Primer consumidor real: `release-scribe` (sem. 3).