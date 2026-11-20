"""agent-loop — loop con herramientas, confirmación explícita y presupuesto (ADR-11).

La hoja no cambia: el runner no llama a ningún modelo. El "cerebro" —quien decide la
próxima acción— es un callable inyectado (un cierre sobre `LlmClient` en producción,
un guion en los tests). Sin cerebro inyectado no hay loop: determinismo por
construcción (D4), como `bot-base`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

ToolFn = Callable[[dict[str, Any]], str]


class ToolSpec(BaseModel):
    """Lo que el cerebro ve de una herramienta: nombre y descripción, no la función."""

    name: str
    description: str


class ToolRegistry:
    """Herramientas con nombre; ejecutar una desconocida es error visible."""

    def __init__(self) -> None:
        self._tools: dict[str, tuple[str, ToolFn]] = {}

    def register(self, name: str, description: str, fn: ToolFn) -> None:
        if name in self._tools:
            raise ValueError(f"herramienta duplicada: {name}")
        self._tools[name] = (description, fn)

    def spec(self) -> list[ToolSpec]:
        return [ToolSpec(name=n, description=d) for n, (d, _) in sorted(self._tools.items())]

    def run(self, name: str, args: dict[str, Any]) -> str:
        if name not in self._tools:
            raise KeyError(f"herramienta desconocida: {name}")
        _, fn = self._tools[name]
        return fn(args)


class Action(BaseModel):
    """Una propuesta del cerebro: usar una herramienta o terminar."""

    razon: str = ""
    tool: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    final: str | None = None

    @property
    def es_final(self) -> bool:
        return self.tool is None


class Step(BaseModel):
    """Un paso ejecutado, con su salida o su error. Nada se corta en silencio."""

    n: int
    accion: Action
    estado: Literal["ok", "rechazado", "error", "final"]
    salida: str | None = None
    detalle: str | None = None


class AgentTrace(BaseModel):
    """La corrida completa: la evidencia de qué hizo el agente y por qué paró."""

    goal: str
    steps: list[Step] = []
    final: str | None = None
    paro: Literal["done", "rechazado", "presupuesto"] = "presupuesto"


Brain = Callable[[dict[str, Any]], Action]
"""Recibe {goal, tools, transcript, step} y propone la próxima Action."""

Confirm = Callable[[Action], bool]
"""Puerta humana: si dice no, el paso queda rechazado y el loop termina."""


def run_agent(
    goal: str,
    *,
    registry: ToolRegistry,
    brain: Brain,
    confirm: Confirm | None = None,
    max_steps: int = 8,
) -> AgentTrace:
    """Corre el loop hasta `done`, un rechazo o agotar el presupuesto de pasos.

    - Una herramienta que falla NO mata el loop: el paso queda `error` con su detalle
      y el cerebro decide la siguiente (puede cambiar de ruta o terminar).
    - `confirm` corre ANTES de ejecutar la herramienta; un `False` termina con
      `paro="rechazado"` — el agente no insiste.
    - El presupuesto es de pasos propuestos: sin `max_steps` el loop podría vivir
      para siempre (ADR-11 §2).
    """
    trace = AgentTrace(goal=goal)
    for n in range(1, max_steps + 1):
        vista = {
            "goal": goal,
            "tools": [t.model_dump() for t in registry.spec()],
            "transcript": [s.model_dump() for s in trace.steps],
            "step": n,
        }
        action = brain(vista)
        if action.es_final:
            trace.steps.append(Step(n=n, accion=action, estado="final"))
            trace.final = action.final
            trace.paro = "done"
            return trace
        if confirm is not None and not confirm(action):
            trace.steps.append(Step(n=n, accion=action, estado="rechazado", detalle="confirmación denegada"))
            trace.paro = "rechazado"
            return trace
        try:
            salida = registry.run(action.tool, action.args)
        except Exception as exc:  # noqa: BLE001 — el error de una herramienta es del paso, no del loop
            trace.steps.append(Step(n=n, accion=action, estado="error", detalle=f"{type(exc).__name__}: {exc}"))
            continue
        trace.steps.append(Step(n=n, accion=action, estado="ok", salida=salida[:2000]))
    trace.paro = "presupuesto"
    return trace
