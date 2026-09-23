"""Horario de recurrencia (ADR-8). Un `Schedule` decide cuándo una tarea debe
correr: cada N segundos de reloj monótono o bajo un predicado de calendario
(`when(now)`). Si no hay `last_run`, la tarea arranca "debida" (`first_run`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable


class Schedule:
    def __init__(
        self,
        every_seconds: float | None = None,
        *,
        when: Callable[[datetime], bool] | None = None,
    ) -> None:
        if every_seconds is None and when is None:
            raise ValueError("Schedule necesita `every_seconds` o `when`")
        if every_seconds is not None and every_seconds <= 0:
            raise ValueError(f"every_seconds debe ser > 0, recibido {every_seconds!r}")
        self.every_seconds = every_seconds
        self.when = when

    def is_due(self, now_monotonic: float, last_run_monotonic: float | None, now: datetime) -> bool:
        if last_run_monotonic is None:
            return True
        if self.when is not None:
            return bool(self.when(now))
        return (now_monotonic - last_run_monotonic) >= (self.every_seconds or 0.0)