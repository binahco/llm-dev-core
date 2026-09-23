"""Persistencia de "última corrida" (ADR-8): la idempotencia del bot.

`JsonRunStore` guarda `{task_id: timestamp_iso}` en un JSON pequeño; el bot la
usa para no repetir una tarea ya corrida (o no pasarla hasta el siguiente
intervalo). Las escrituras son atómicas (tmp + replace).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Protocol

from .clock import RealClock


class RunStore(Protocol):
    def last_run(self, task_id: str) -> float | None: ...

    def mark_done(self, task_id: str, at_monotonic: float) -> None: ...


class JsonRunStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._state: dict[str, str] = {}
        if self._path.exists():
            self._state = json.loads(self._path.read_text(encoding="utf-8"))
        self._clock = RealClock()

    def last_run(self, task_id: str) -> float | None:
        raw = self._state.get(task_id)
        if raw is None:
            return None
        # guardamos el timestamp monótono como str para mantener el JSON plano
        return float(raw)

    def mark_done(self, task_id: str, at_monotonic: float) -> None:
        self._state[task_id] = f"{at_monotonic:.6f}"
        self._flush()

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._state, indent=2, ensure_ascii=False) + "\n"
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self._path.parent, delete=False
        ) as tmp:
            tmp.write(payload)
            tmp_name = tmp.name
        Path(tmp_name).replace(self._path)