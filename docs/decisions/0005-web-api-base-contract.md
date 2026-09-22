# Contrato mínimo — `web-api-base`

- **Fecha:** 2026-09-22
- **Estado:** aceptada
- **Origen:** ADR-0 (`docs/decisions/0000-stack.md` §FastAPI) y C5 en `ARCHITECTURE.md` §5
- **Implementada en:** semana 6 (`packages/web-api-base` v0.1.0, nacida dentro de `eval-api`)

`web-api-base` es el FastAPI LLM-ready del core: la base reutilizable para que un
consumidor exponga capacidades LLM por HTTP sin reinventar el cableado que une
`llm-client`, `schema-validate` y el contrato de errores del pipeline.

## 1. API conceptual

```python
create_app(title, version, *, client: LlmClient,
           health_extra=None, llm_path="/llm", enable_llm_endpoint=True) -> FastAPI
```

Endpoints base:

| Ruta | Comportamiento |
|---|---|
| `GET /health` | liveness: `{status, service, core_version, provider, model_alias}` |
| `POST /llm` | pipeline LLM completo: request → render → `client.complete` → validación → respuesta |
| `GET /docs` | OpenAPI (FastAPI nativo) |

Contrato de entrada del endpoint LLM:

```python
class CompleteRequest(BaseModel):
    prompt_id: str
    prompt_version: str | None = None
    variables: dict = {}
    model_alias: str = "fast"
    response_schema: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    tags: list[str] = []
```

Contrato de salida del endpoint LLM (`LLMResultBody`): `span_id`, `prompt_id`,
`prompt_version`, `model`, `provider`, `content` (raw), `parsed` (validado), `validation_ok`,
`validation_errors`, `cost_usd`, `latency_ms`.

Errores uniformes:

| Condición | Código | `error` |
|---|---|---|
| Salida que no valida contra `response_schema` | 422 | `salida_no_validada` |
| Request no válido | 422 | `peticion_invalida` |
| `CostCapExceeded` | 429 | `presupuesto_excedido` |
| Fallo de proveedor/red | 502 | `proveedor_indisponible` |
| Cualquiera otra | 500 | `error_interno` |

Conveniencia: `sse_response(client, req, *)` devuelve un `StreamingResponse`
`text/event-stream` con los mismos contratos (evento `data:` con el JSON y al final
`event: done`).

## 2. Reglas

- **La regla 3 es el gate (§3.1):** por defecto, un `response_schema` declarado exige
  `validation.ok` antes de responder. `require_valid=False` es un opt-out explícito
  (para endpoints de debug, no de producción).
- **`web-api-base` no importa `test-kit`:** la evaluación de prompts es un consumidor
  más (viaja a `eval-api` como composición), no una capacidad de la base.
- **Composición, no acoplamiento:** la base recibe el `client` construido por el
  consumidor (con su `renderer`, `validator` y `emitter`). La base no sabe renderizar
  prompts ni registrar schemas.

## 3. Qué NO contrata este documento

- Auth (llega con `auth-base`, sem 25), rate-limit/cache (`cache-ratelimit`, sem 8) y
  observabilidad agregada (`cost-obs`, sem 39) — la base solo deja el hook (`emitter`
  del cliente y los campos del span).
- Streaming por token: `llm-client` entrega resultados completos (retries/reparación
  internos); aquí el SSE es por-evento, no por-token.

## 4. Criterio de aceptación del contrato (semana 6)

- [x] `/health` devuelve estado, versión y proveedor del cliente.
- [x] `POST /llm` con `response_schema` válido y salida validada → 200 con `parsed`.
- [x] Salida que no valida → 422 `salida_no_validada` (la base nunca responde JSON del
      LLM sin pasar por `schema-validate`).
- [x] `CostCapExceeded` → 429; request mal formado → 422; excepción inesperada → 500.
- [x] `sse_response` emite el resultado como `data:` + `event: done`.
- [x] Primer consumidor real: `eval-api` (sem. 6), que reusa `llm-client` +
      `schema-validate` + `test-kit` + `web-api-base` para evaluar prompts por HTTP.