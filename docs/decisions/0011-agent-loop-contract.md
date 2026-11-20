# Contrato mínimo — `agent-loop`

- **Fecha:** 2026-11-20
- **Estado:** aceptada
- **Origen:** el calendario C1–C18 (§5): `agent-loop` (C13) es la base del agente con
  herramientas del reto. No es un chatbot ni un orquestador de gráficos: es **el loop
  mínimo con puerta humana** — proponer, confirmar, ejecutar, registrar.
- **Implementada en:** semana 21 (`packages/agent-loop` v0.1.0, dentro de `llm-dev-core`
  v1.3.0; primer consumidor: `checklist-walker`)

Un "agente" sin confirmación es un `rm -rf` con buena retórica. Lo que la flota necesita
antes de autonomía es el esqueleto honesto: un loop donde cada acción con efecto pasa por
una puerta explícita, donde el error de una herramienta no mata la corrida, y donde todo
queda en un trace auditable.

## 1. API conceptual

```python
from agent_loop import Action, ToolRegistry, run_agent

registry = ToolRegistry()
registry.register("leer", "lee un archivo", fn)          # (nombre, descripción, callable)

trace = run_agent(
    "verificar el repo",
    registry=registry,
    brain=mi_cerebro,          # dict(vista) -> Action: la próxima acción
    confirm=lambda a: False,   # puerta humana antes de ejecutar (None = sin puerta)
    max_steps=8,               # presupuesto de pasos propuestos
)
trace.paro    # "done" | "rechazado" | "presupuesto"
trace.steps   # [{n, accion, estado, salida|detalle}] — la corrida completa
```

## 2. Reglas

- **La hoja no cambia y el runner es agnóstico:** `agent-loop` no depende de ningún
  módulo del core (solo `pydantic`) ni llama a ningún modelo. El "cerebro" es un
  callable inyectado — un cierre sobre `LlmClient` en producción, un guion en los
  tests. Determinismo por construcción (D4), como `bot-base`.
- **Confirmación explícita antes del efecto:** `confirm(action) -> bool` corre antes
  de ejecutar la herramienta; un `False` termina con `paro="rechazado"` — el agente
  no insiste ni reintenta la puerta. Sin `confirm`, el consumidor decidió no poner
  puerta y lo firma.
- **El error de una herramienta es del paso, no del loop:** el paso queda `error`
  con su detalle y el cerebro decide la siguiente acción (cambiar de ruta o terminar).
  Nada se corta en silencio (§5.1).
- **Presupuesto de pasos obligatorio:** sin `max_steps` el loop podría vivir para
  siempre; agotado el presupuesto, `paro="presupuesto"` — visible, no un timeout.
- **El trace es la evidencia:** cada paso lleva acción propuesta (con su razón),
  estado y salida acotada. Quien audita no necesita volver a correr el agente.

## 3. Qué NO contrata este documento

- **El cerebro:** cómo el LLM elige herramientas es problema del consumidor (componer
  `llm-client` + `schema-validate`); aquí solo se exige que devuelva `Action`.
- **Memoria entre corridas ni planificación multi-agente:** un loop, un goal, un trace.
- **Efectos compensables (rollback):** la puerta está antes del efecto; deshacer no
  es de esta capa.
- **Paralelismo de herramientas:** pasos en serie; lo demás cuando dos consumidores
  lo necesiten (D12).

## 4. Criterio de aceptación del contrato (semana 21)

- [x] `ToolRegistry` con spec visible para el cerebro (nombre + descripción, nunca la
      función) y error visible en duplicadas/desconocidas.
- [x] `run_agent` con cerebro inyectado, confirmación, presupuesto y trace completo.
- [x] Error de herramienta no mata el loop; rechazo termina sin insistir.
- [x] Primer consumidor real: `checklist-walker` (sem. 21) — camina un checklist con
      herramientas de lectura sobre un repo real y reporta con LLM validado.
