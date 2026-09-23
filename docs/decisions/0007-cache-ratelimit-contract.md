# Contrato mínimo — `cache-ratelimit`

- **Fecha:** 2026-09-23
- **Estado:** aceptada
- **Origen:** §2.4 de `ARCHITECTURE.md` ("el acceso externo respeta límites: rate
  limiting, caché, robots.txt"), y la promesa de costo/ritmo de §8.1 — el `429
  presupuesto_excedido` de `web-api-base` es de *presupuesto*, no de *ritmo*.
- **Implementada en:** semana 8 (`packages/cache-ratelimit` v0.1.0, nacida dentro de
  `llm-gateway`)

`llm-client` es la hoja (regla 1 de §3): no toca a nadie ni nadie puede obligarla a
cambiarse. La caché y el ritmo son **política de composición**: viven en providers
envueltos, como `ReplayProvider`. `cache-ratelimit` formaliza esa capa.

## 1. API conceptual

```python
from cache_ratelimit import RateLimiter, ThrottledProvider, CachedProvider

# token bucket con reloj inyectable (determinista en tests y CI, D4):
limiter = RateLimiter(rpm=60, burst=12, clock=my_clock)   # 60 llamadas/minuto, ráfaga 12
limiter.acquire()                                          # espera si el bucket está vacío
limiter.stats()  # {"rpm", "burst", "tokens", "calls", "blocked_calls", "total_wait_seconds"}

# caché con TTL a nivel de provider (los streams nunca se cachean):
cached = CachedProvider(inner, ttl_seconds=600.0, clock=my_clock)
cached.stats()  # {"ttl_seconds", "entries", "hits", "misses"}

# composición, como los otros wrappers:
provider = ThrottledProvider(CachedProvider(inner, ttl_seconds=600.0), RateLimiter(rpm=60))
client = LlmClient(provider, ...)
```

Ambos wrappers implementan `llm_client.provider.Provider` (`complete`/`stream`), igual
que `ReplayProvider` y los transportes — se enchufan donde hoy se enchufa cualquier
provider. El `cache_hit` del span es responsabilidad del `LlmClient` (caché a nivel
cliente, si se usa); el `CachedProvider` no toca el span.

## 2. Reglas

- **La hoja no cambia:** `cache-ratelimit` depende solo de `llm-dev-client` (protocolo
  `Provider`, modelos de request/response). Nada de `schema-validate`, `test-kit` ni
  `web-api-base`; los `429` son de la capa HTTP del consumidor (web-api-base los mapéa).
- **El ritmo se mide en tokens, no en peticiones-servicio:** `rpm` es llamadas al
  *proveedor* por minuto; un hit de caché no consume token (no cruza al proveedor).
- **Determinismo (D4):** el reloj es un protocolo (`monotonic`/`sleep`); los tests usan
  un reloj falso que nunca bloquea de verdad. En producción, `RealClock`.
- **Los streams existen pero no se cachean:** para un flujo de tokens, cachear el primer
  chunk no sirve; v1 los deja pasar con su token del bucket y cuenta miss.
- **Poda por expiración:** TTL por entrada; `complete` poda vencidos de paso (sin
  background thread, sin busy-wait).

## 3. Qué NO contrata este documento

- La **caché a nivel cliente** de `llm-client` (`ResponseCache`, `cache_key`) sigue
  intacta — son dos capas distintas: `llm-client.cache` es contrato de la hoja;
  `CachedProvider` es política del consumidor.
- **Persistencia/evicción LRU** y campos nuevos del span (`throttle_wait_ms`,
  cache/rate del gateway) quedan para el segundo consumidor o `cost-obs` (sem. 39).
- La **UI de monitoreo** del gateway (estado del bucket) es del consumidor, no del core.

## 4. Criterio de aceptación del contrato (semana 8)

- [x] `RateLimiter` respeta `rpm` y `burst` con reloj inyectable; `stats()` exactas.
- [x] `ThrottledProvider` espera el bucket antes de `complete`/`stream` y deja pasar el hit.
- [x] `CachedProvider` cachea `complete` idéntico (hit/miss), expira por TTL y poda vencidos.
- [x] La composición `ThrottledProvider(CachedProvider(inner))` funciona sin tocar `llm-client`.
- [x] Primer consumidor real: `llm-gateway` (sem. 8), que expone `/llm` de `web-api-base`
      con la cadena cache+throttle y una ruta `/gateway/stats`.