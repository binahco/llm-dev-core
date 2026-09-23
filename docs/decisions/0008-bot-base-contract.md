# Contrato mínimo — `bot-base`

- **Fecha:** 2026-09-30
- **Estado:** aceptada
- **Origen:** el calendario C1–C18 (§5): `bot-base` (C8) es la base de las tareas
  recurrente de la flota. No es un bot de chat (llega `gh-app`, sem. 27) ni un
  agente autónomo con herramientas (`agent-loop`, sem. 21): es la **recurrencia
  programada determinista**.
- **Implementada en:** semana 9 (`packages/bot-base` v0.1.0, nacida dentro de
  `fleet-bot`)

La flota corre un `eval-smoke` diario (`§8.1`) y la evidencia se regenera cada
`make validate`: tareas repetitivas con LLM. Hoy "quién las dispara" es el
mantenedor a mano. `bot-base` formaliza esa capa: un horario, una memoria de
última corrida y un digest — deterministas por construcción (D4).

## 1. API conceptual

```python
from bot_base import JsonRunStore, Schedule, Task, run_tasks

store = JsonRunStore(".bot/state.json")          # idempotencia persistente

digest = run_tasks(
    [
        Task("audit",  Schedule(every_seconds=86400), run=run_audit_ci_pack),
        Task("digest", Schedule(every_seconds=86400), run=run_digest_llm),
    ],
    store=store,
    clock=my_clock,                              # inyectable: tests deterministas
)
digest.text()   # "2 ok · 0 skipped · 0 failed\n- audit: ok — …\n- digest: ok — …"
```

- `Schedule(every_seconds=N)` o `Schedule(when=callable_de_calendario)`;
  `is_due(now_monotonic, last_run, now)` decide. Sin `last_run` → debida.
- `run_tasks` corre cada tarea debida una vez (`RunStore.last_run`/`mark_done`),
  captura fallos en el `Digest` y **no** marca `done` lo que falló.
- El runner **no llama a un LLM**: `Task.run` es un callable del consumidor
  (p. ej. un cierre que usa `LlmClient`). La novedad de la semana es la
  recurrencia (D9); el LLM se compone.

## 2. Reglas

- **La hoja no cambia y el runner es agnóstico:** `bot-base` no depende de
  `llm-client` ni de ningún módulo del core (solo `pydantic` + stdlib); la tarea
  LLM es composición del consumidor, como `cache-ratelimit` no toca la hoja.
- **Determinismo (D4):** `BotClock` (`monotonic`/`sleep`/`now`) se inyecta; los
  tests usan un `FakeClock` que nunca duerme y avanza a mano. Los horarios
  "cada N" usan reloj monótono; las reglas de calendario ("el lunes") usan `now()`.
- **Idempotencia explícita:** sin `RunStore` el runner repetiría; con él, una
  tarea ya corrida en su intervalo es `skipped` y no se vuelve a pagar.
- **Fallos visibles:** el `Digest` es el estado de la corrida (ok/skipped/failed
  con detalle de una línea); el consumidor decide si un fallo re-dispara (hook
  futuro de `ci-pack`/`cost-obs`). Nada se corta en silencio (§5.1).
- **Persistencia atómica:** `JsonRunStore` escribe tmp+replace; un bot matado a
  media escritura no corrompe el estado.

## 3. Qué NO contrata este documento

- Un **daemon/scheduler de reloj** (launchd/cron/GH Actions lo transporta): el
  runner es una función que el consumidor dispara cuando quiera.
- El **loop de agente** con herramientas y confirmación explícita — `agent-loop`
  (sem. 21); `bot-base` no ejecuta herramientas, corre tareas.
- **Retry/presupuesto/caché** por tarea: viven en `llm-client` (cap de costo) y
  `cache-ratelimit`, compuestos en el consumidor.
- **Observabilidad agregada** de corridas: `cost-obs` (sem. 39).

## 4. Criterio de aceptación del contrato (semana 9)

- [x] `Schedule` con intervalos y predicado de calendario; `is_due` determinista.
- [x] `run_tasks` corre una vez, respeta idempotencia, no marca `done` lo fallido.
- [x] `Digest.text()` es el resumen de una línea por tarea.
- [x] `JsonRunStore` persiste y recarga; escritura atómica.
- [x] Pimer consumidor real: `fleet-bot` (sem. 9) — ciclo matutino de
      audit + evidencia + digest LLM con lock de día en `.bot/state.json`.