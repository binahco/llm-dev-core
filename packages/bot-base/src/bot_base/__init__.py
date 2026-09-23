"""bot-base: recurrencia programada determinista e idempotente (ADR-8).

El bot de la flota (sem. 9) corre tareas LLM todos los días con relojes
inyectables y un store de última corrida; `run_tasks` decide qué toca y
devuelve un `Digest` para el resumen. El runner no llama a un LLM: la tarea
es composición del consumidor (novedad acotada a la recurrencia, D9).

    from bot_base import JsonRunStore, Schedule, Task, run_tasks

    store = JsonRunStore(".bot/state.json")
    digest = run_tasks(
        [Task("audit", Schedule(every_seconds=86400), run=run_audit)],
        store=store, clock=my_clock,
    )
"""

from .clock import BotClock, RealClock
from .digest import Digest, TaskResult
from .runner import Task, run_tasks
from .schedule import Schedule
from .store import JsonRunStore, RunStore

__all__ = [
    "BotClock",
    "Digest",
    "JsonRunStore",
    "RealClock",
    "RunStore",
    "Schedule",
    "Task",
    "TaskResult",
    "run_tasks",
]