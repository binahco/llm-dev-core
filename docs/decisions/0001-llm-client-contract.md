# Contrato mínimo — `llm-client`

- **Fecha:** 2026-09-20
- **Estado:** propuesta (se congela en la semana 2, cuando `llm-client` nazca dentro del CLI de commits)
- **Origen:** D4 en `ARCHITECTURE.md`

Este documento es el contrato escrito contra el que se implementa la semana 2. Define la API conceptual, el schema de span (contrato público desde el día 1) y la interfaz de proveedor con backend record/replay. Los nombres son orientativos; los contratos que se congelan son los campos del span y los límites del behavior.

## 1. API conceptual

```python
class LlmClient:
    def complete(self, request: CompletionRequest) -> CompletionResult: ...
    def stream(self, request: CompletionRequest) -> Iterator[CompletionChunk]: ...
```

```python
class CompletionRequest:
    prompt_id: str
    prompt_version: str | None = None        # default: latest de prompt-registry
    variables: dict[str, Any]                # para renderizar el prompt
    model_alias: str
    response_schema: SchemaId                # valida contra schema-validate
    temperature: float | None = None
    max_tokens: int | None = None
    tags: list[str] = []                     # para agrupar costos por feature
```

```python
class CompletionResult:
    raw_text: str
    parsed: Any | None                       # salida validada (schema-validate)
    validation: ValidationResult
    usage: TokenUsage                        # tokens_input, tokens_output
    cost_usd: Decimal
    latency_ms: int
    prompt_id: str
    prompt_version: str
    model_alias: str
    model: str                               # modelo real resuelto por el alias
    provider: str
    span_id: str
```

Límites de comportamiento (invariantes de `llm-client`):

- Retry automático con backoff exponencial y jitter; contado en el span (`retry_count`).
- Streaming disponible en la API, no solo en el SDK del proveedor.
- Record/replay nativo: `complete`/`stream` se pueden ejecutar contra un cassette (ver §4).
- Todo objeto no válido entra a la reparación definida en D5, con tope de 2 intentos y cap de costo.
- Nunca loguea el contenido de `variables` en claro con datos sensibles (redacción de §3.1).

## 2. Schema del span (contrato público, semana 2 en adelante)

Este schema es **API pública** del core desde el día 1. `cost-obs` (sem. 39) lo lee; los consumidores lo emiten sin configurar nada.

Campos mínimos, serializados como una línea JSON por llamada:

```text
span_id                              uuid
trace_id                             uuid (correlaciona upstream/downstream)
consumer_repo                        str (repo semanal: "commit-cli")
prompt_id                            str
prompt_version                       str  (semver del prompt)
model_alias                          str  ("fast" | "smart" | ...)
model                                str  (modelo real, p. ej. "gpt-4o-mini")
provider                             str  (p. ej. "openai")
tokens_input                         int
tokens_output                        int
latency_ms                           int
cost_usd                             Decimal
retry_count                          int  (0 = primera vez)
cache_hit                            bool
status                               str  (ok | repaired | failed | skipped)
call_skipped                         bool (la llamada no se necesitaba: cache, dedup)
retry_unnecessary                    bool (la primera respuesta ya era válida, se reintentó igual)
error_type                           str | null
repaired_attempts                    int  (reparaciones D5 consumidas)
timestamp                            ISO-8601
```

`call_skipped` y `retry_unnecessary` responden la pregunta de la semana 39: no cuánto costó la llamada, sino **si se necesitaba**. El log de costo dice cuánto gastaste; el log de utilidad dice cuánto tiraste.

El dashboard (`cost-obs`) puede esperar; el schema no. Cambiar este schema después de la semana 2 es un breaking change de contrato con sus consumidores, sujeto a §6.1 de `ARCHITECTURE.md`.

## 3. Interfaz de proveedor

```python
class Provider(Protocol):
    def complete(self, request: ProviderRequest) -> ProviderResponse: ...
    def stream(self, request: ProviderRequest) -> Iterable[ProviderChunk]: ...
```

`llm-client` se compone con proveedores; no los engloba dentro del mismo objeto. Cada proveedor:

- Resuelve `model_alias` → `model` real conociendo el pricing (para `cost_usd`).
- Declara sus capacidades (JSON mode, streaming, costos por token).

## 4. Backend record/replay (nativo desde la semana 2)

El schema del span no es lo único no-retrofitteable: también lo es poder **grabar y reproducir** llamadas.

- `llm-client` acepta un `Provider` envuelto en `ReplayProvider`.
- **Record:** ejecuta contra la API real y guarda el cassette (petición → respuesta + span).
- **Replay:** sirve la respuesta desde el cassette sin tocar la API; las llamadas no presentes fallan de forma ruidosa.
- Sin API keys en CI. Sin golpear APIs vivas en evals (D7) ni en compat check (D8).

`test-kit` (sem. 5) implementa el formato de cassette; el compat check (sem. 13) lo consume.

## 5. Qué NO contrata este documento

- No define formatos de cassette (sem. 5, `test-kit`).
- No define el renderizado ni la resolución de prompts (sem. 35, `prompt-registry` fase 2).
- No define la reparación de esquemas (sem. 3, `schema-validate`), solo su tope.
- No define dónde cae el log (consumidor o core): solo el schema. `cost-obs` (sem. 39) decide el transporte.

## 6. Criterio de aceptación del contrato (semana 2)

- [ ] `uv run pytest` verde con un test de `complete` y uno de `stream` vía replay.
- [ ] Un cassette grabado se reproduce sin API key.
- [ ] El span emitido cumple §2 campo por campo.
- [ ] `call_skipped` y `retry_unnecessary` se emiten correctamente en los casos forzados.