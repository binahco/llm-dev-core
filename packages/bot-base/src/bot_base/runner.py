"""Runner del bot (ADR-8): una tarea es un callable + un horario.

`run_tasks` respeta el horario y la idempotencia (RunStore) y devuelve un
`Digest`. El runner NO sabe qué es un LLM: la tarea es composición del
consumidor (p. ej. un cierre que llama a `client.complete`); así la novedad
de la semana queda en la recurrencia (D9).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .clock import BotClock, RealClock
from .digest import Digest, TaskResult
from .schedule import Schedule
from .store import RunStore


@dataclass
class Task:
    id: str
    schedule: Schedule
    run: Callable[[], str]


def run_tasks(tasks: list[Task], *, store: RunStore, clock: BotClock | None = None) -> Digest:
    clock = clock if clock is not None else RealClock()
    now_monotonic = clock.monotonic()
    now = clock.now()
    results: list[TaskResult] = []

    for task in tasks:
        last = store.last_run(task.id)
        if not task.schedule.is_due(now_monotonic, last, now):
            results.append(TaskResult(task_id=task.id, status="skipped", detail="no debe aún"))
            continue
        try:
            detail = task.run()
        except Exception as exc:  # noqa: BLE001
            results.append(TaskResult(task_id=task.id, status="failed", detail=f"{type(exc).__name__}: {exc}"))
            continue
        store.mark_done(task.id, now_monotonic)
        results.append(TaskResult(task_id=task.id, status="ok", detail=detail))

    return Digest(results=results)